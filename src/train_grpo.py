"""
train_grpo.py -- RL with a verifier-gated reward (v4.1 plan, W6 optional RL).

Runs in a training environment (requirements-train.txt) (torch 2.5.1, transformers 4.53.3, trl 0.19.1,
peft 0.15.2). fp32 (the P100 has no bf16 and fp16 diverged for Qwen3).

Reward for a completion = 1 if the IE label calls it correct AND the chosen
verifier accepts it, else 0. Conditions (--verifier):
  label        no verifier (reward = label only)
  certified    the certified synthesised verifier (report's pre-specified rule)
  f1           the F1-selected verifier (uncertified)
  handwritten  version3's hand-written stack
Logged every step to --log: mean reward, fraction of completions with a
non-empty "else" field, fraction of correct-but-rejected completions.
After training: greedy decoding of the test prompts to --out.

  python src/train_grpo.py --verifier f1 --seed 0 \
      --out data/rl/gen_ie_f1_s0.jsonl --log data/rl/log_ie_f1_s0.jsonl
"""
import argparse, json, os, random, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO = os.path.dirname(HERE)   # data/ and out/ live at the repo root

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model

from soundver import generate as g
from soundver.checks import ie_parses


def load_verifier(name):
    if name == "label":
        return []
    curve = json.load(open(os.path.join(REPO, "out/curve_ie_inst_multi.json")))["results"]
    sel = {r["selection"]: r["checks"] for r in curve}
    if name == "f1":
        return sel["f1_baseline"]
    if name == "handwritten":
        return sel["handwritten"]
    for b in (0.01, 0.02, 0.05):                 # same pre-specified rule as certver.report
        r = [x for x in curve if x["selection"] == f"itau={b}"][0]
        if r["certified"]:
            return r["checks"]
    raise SystemExit("no certified selection")


def compile_checks(ids):
    """Synthesised checks were validated by the sandbox and run on >40k
    outputs; here they are executed in-process for speed."""
    src = {}
    for p in __import__("glob").glob(os.path.join(REPO, "out/candidates/ie_*.jsonl")):
        for line in open(p):
            if line.strip():
                c = json.loads(line); src[c["id"]] = c["source"]
    fns = []
    for cid in ids:
        if cid.startswith("hw:"):
            name = cid[3:]
            fns.append(lambda raw, item, name=name: bool(g.score_checks("ie", raw, item)[0][name]))
        else:
            ns = {"parse_json": lambda raw: ie_parses(g._ie_extract_json(raw))}
            exec(compile(src[cid], cid, "exec"), ns)  # noqa: S102
            f = ns["check"]

            def run(raw, item, f=f):
                try:
                    v = f(raw, {"text": item["text"]})
                    return v if isinstance(v, bool) else False
                except Exception:  # fail closed, as in the sandbox
                    return False
            fns.append(run)
    return fns


def load_base(a):
    model = AutoModelForCausalLM.from_pretrained(a.model, torch_dtype=torch.float32).to("cuda")
    if a.init_adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, a.init_adapter).merge_and_unload()
    return model


def chat(tok, prompt):
    return tok.apply_chat_template([{"role": "user", "content": prompt}], tokenize=False,
                                   add_generation_prompt=True, enable_thinking=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verifier", required=True, choices=["label", "certified", "f1", "handwritten"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--prompts-per-step", type=int, default=8)
    ap.add_argument("--generations", type=int, default=8)
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--model", default="Qwen/Qwen3-0.6B")
    ap.add_argument("--train", default=os.path.join(REPO, "data/distill/pool_ie_distill_seed0.items.jsonl"))
    ap.add_argument("--eval", default=os.path.join(REPO, "data/distill/eval_ie_prompts.jsonl"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--eval-only", action="store_true", help="greedy-decode the base model, no training")
    ap.add_argument("--init-adapter", default=None,
                    help="LoRA adapter (e.g. an SFT student) merged into the base model before RL")
    a = ap.parse_args()
    random.seed(a.seed); torch.manual_seed(a.seed)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    tok = AutoTokenizer.from_pretrained(a.model)
    tok.padding_side = "left"
    items = {json.loads(l)["instance_id"]: json.loads(l) for l in open(a.train) if l.strip()}

    if not a.eval_only:
        checks = compile_checks(load_verifier(a.verifier))
        rows = [{"prompt": chat(tok, g.PROMPTS["ie"](it, "base")), "instance_id": iid}
                for iid, it in items.items()]
        random.shuffle(rows)
        logf = open(a.log, "w")

        def reward(prompts, completions, instance_id, **kw):
            out, n_else, n_cr = [], 0, 0
            for comp, iid in zip(completions, instance_id):
                it = items[iid]
                obj = ie_parses(g._ie_extract_json(comp))
                correct = g._field_value_match(obj if isinstance(obj, dict) else None, it["gold"])
                accepted = all(f(comp, it) for f in checks)
                if isinstance(obj, dict) and obj.get("else"):
                    n_else += 1
                if correct and not accepted:
                    n_cr += 1
                out.append(1.0 if (correct and accepted) else 0.0)
            logf.write(json.dumps({"t": time.time(), "n": len(out), "sample": str(completions[0])[:300],
                                   "reward": sum(out) / len(out),
                                   "else_rate": n_else / len(out),
                                   "correct_rejected_rate": n_cr / len(out)}) + "\n")
            logf.flush()
            return out

        model = load_base(a)
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()
        model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.0, task_type="CAUSAL_LM",
                                                 target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                                                 "gate_proj", "up_proj", "down_proj"]))
        opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.0)
        order = list(range(len(rows))); random.shuffle(order); k = 0
        t0 = time.time()
        for step in range(a.steps):
            batch = []
            for _ in range(a.prompts_per_step):
                if k >= len(order):
                    random.shuffle(order); k = 0
                batch.append(rows[order[k]]); k += 1
            # ---- generate (eval mode, KV cache), G samples per prompt
            model.eval()
            groups = []
            with torch.no_grad():
                for r in batch:
                    enc = tok([r["prompt"]] * a.generations, return_tensors="pt", padding=True,
                              add_special_tokens=False).to("cuda")
                    out = model.generate(**enc, do_sample=True, temperature=1.0, top_p=1.0, top_k=0,
                                         max_new_tokens=160, pad_token_id=tok.pad_token_id, use_cache=True)
                    comp_ids = out[:, enc["input_ids"].shape[1]:]
                    texts = tok.batch_decode(comp_ids, skip_special_tokens=True)
                    rw = reward([r["prompt"]] * a.generations, texts, [r["instance_id"]] * a.generations)
                    groups.append((enc["input_ids"][0][enc["attention_mask"][0].bool()], comp_ids, rw))
            # ---- policy gradient with group-normalised advantages (single on-policy update)
            model.train()
            opt.zero_grad()
            n_used = 0
            for prompt_ids, comp_ids, rw in groups:
                rwt = torch.tensor(rw, device="cuda")
                if rwt.std() < 1e-6:
                    continue                      # no learning signal in this group
                adv = (rwt - rwt.mean()) / (rwt.std() + 1e-4)
                for j in range(comp_ids.shape[0]):
                    c = comp_ids[j]
                    L = int((c != tok.pad_token_id).sum().item())
                    eos = (c == tok.eos_token_id).nonzero()
                    L = int(eos[0].item()) + 1 if len(eos) else c.shape[0]
                    if L == 0:
                        continue
                    ids = torch.cat([prompt_ids, c[:L]]).unsqueeze(0)
                    logits = model(input_ids=ids).logits[0, prompt_ids.shape[0] - 1:-1]
                    lp = torch.log_softmax(logits.float(), -1).gather(1, c[:L].unsqueeze(1)).squeeze(1)
                    loss = -(adv[j] * lp.mean()) / (len(groups) * comp_ids.shape[0])
                    loss.backward()
                    n_used += 1
            if n_used:
                torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
                opt.step()
            if step % 5 == 0 or step == a.steps - 1:
                print(f"step {step + 1}/{a.steps} groups_with_signal={sum(1 for _, _, rw in groups if len(set(rw)) > 1)}"
                      f" mean_reward={sum(sum(rw) for _, _, rw in groups) / (len(groups) * a.generations):.3f}"
                      f" {time.time() - t0:.0f}s", flush=True)
        logf.close()
    else:
        model = load_base(a)
    model = model.to("cuda").eval()
    evals = [json.loads(l) for l in open(a.eval) if l.strip()]
    with open(a.out, "w") as f, torch.no_grad():
        for i in range(0, len(evals), 16):
            chunk = evals[i:i + 16]
            enc = tok([chat(tok, r["prompt"]) for r in chunk], return_tensors="pt", padding=True,
                      add_special_tokens=False).to("cuda")
            gen = model.generate(**enc, max_new_tokens=256, do_sample=False, pad_token_id=tok.pad_token_id)
            for r, s in zip(chunk, gen):
                f.write(json.dumps({"instance_id": r["instance_id"],
                                    "output": tok.decode(s[enc["input_ids"].shape[1]:], skip_special_tokens=True)}) + "\n")
    print("done", a.verifier, a.seed)


if __name__ == "__main__":
    main()
