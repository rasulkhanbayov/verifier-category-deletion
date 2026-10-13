"""
train_sft.py -- LoRA fine-tune a small student on one filtered training set,
then greedy-decode the test prompts. Runs in a training environment (requirements-train.txt) (torch 2.5.1,
transformers 4.53, peft 0.15); standalone, no certver imports.

  python src/train_sft.py --train data/distill/sft_ie_certified.jsonl \
      --eval data/distill/eval_ie_prompts.jsonl --out data/distill/gen_ie_certified.jsonl
"""
import argparse, json, math, os, random, time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model


def chat(tok, prompt, completion=None):
    msgs = [{"role": "user", "content": prompt}]
    text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
                                   enable_thinking=False)
    return text if completion is None else (text, completion + tok.eos_token)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True); ap.add_argument("--eval", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="Qwen/Qwen3-0.6B")
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--batch", type=int, default=8); ap.add_argument("--accum", type=int, default=2)
    ap.add_argument("--max-len", type=int, default=640)
    ap.add_argument("--max-new", type=int, default=256)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--save-adapter", default=None, help="directory to save the trained LoRA adapter")
    ap.add_argument("--fp16", action="store_true",
                    help="fp16 autocast; UNSTABLE for Qwen3 on P100 (NaN loss observed), default is fp32")
    a = ap.parse_args()
    random.seed(a.seed); torch.manual_seed(a.seed)
    dev = "cuda"
    tok = AutoTokenizer.from_pretrained(a.model)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(a.model, torch_dtype=torch.float32).to(dev)
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
                                             target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                                             "gate_proj", "up_proj", "down_proj"]))

    rows = [json.loads(l) for l in open(a.train) if l.strip()]
    data = []
    for r in rows:
        p, c = chat(tok, r["prompt"], r["completion"])
        pi = tok(p, add_special_tokens=False)["input_ids"]
        ci = tok(c, add_special_tokens=False)["input_ids"]
        ids = (pi + ci)[: a.max_len]
        labels = ([-100] * len(pi) + ci)[: a.max_len]
        data.append((ids, labels))
    steps = math.ceil(len(data) * a.epochs / (a.batch * a.accum))
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.0)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / 20) * max(0.0, 1 - s / steps))
    scaler = torch.cuda.amp.GradScaler(enabled=a.fp16)
    model.train()
    order = []
    while len(order) < steps * a.batch * a.accum:
        idx = list(range(len(data))); random.shuffle(idx); order += idx
    t0 = time.time(); k = 0
    for step in range(steps):
        for _ in range(a.accum):
            batch = [data[i] for i in order[k:k + a.batch]]; k += a.batch
            L = max(len(x) for x, _ in batch)
            ids = torch.tensor([[tok.pad_token_id] * (L - len(x)) + x for x, _ in batch], device=dev)
            lab = torch.tensor([[-100] * (L - len(y)) + y for _, y in batch], device=dev)
            att = torch.tensor([[0] * (L - len(x)) + [1] * len(x) for x, _ in batch], device=dev)
            with torch.autocast("cuda", dtype=torch.float16, enabled=a.fp16):
                loss = model(input_ids=ids, attention_mask=att, labels=lab).loss / a.accum
            if not torch.isfinite(loss):
                raise SystemExit(f"non-finite loss at step {step + 1}; aborting")
            scaler.scale(loss).backward()
        scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(opt); scaler.update(); opt.zero_grad(); sched.step()
        if step % 25 == 0 or step == steps - 1:
            print(f"step {step + 1}/{steps} loss {loss.item() * a.accum:.4f} {time.time() - t0:.0f}s", flush=True)

    if a.save_adapter:
        model.save_pretrained(a.save_adapter)
    model.eval()
    evals = [json.loads(l) for l in open(a.eval) if l.strip()]
    out = open(a.out, "w")
    with torch.no_grad():
        for i in range(0, len(evals), 16):
            chunk = evals[i:i + 16]
            enc = tok([chat(tok, r["prompt"]) for r in chunk], return_tensors="pt", padding=True,
                      add_special_tokens=False).to(dev)
            with torch.autocast("cuda", dtype=torch.float16, enabled=a.fp16):
                gen = model.generate(**enc, max_new_tokens=a.max_new, do_sample=False,
                                     pad_token_id=tok.pad_token_id)
            for r, gseq in zip(chunk, gen):
                text = tok.decode(gseq[enc["input_ids"].shape[1]:], skip_special_tokens=True)
                out.write(json.dumps({"instance_id": r["instance_id"], "output": text}) + "\n")
            out.flush()
    out.close()
    print(f"done: {len(data)} train examples, {steps} steps, {len(evals)} eval outputs, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
