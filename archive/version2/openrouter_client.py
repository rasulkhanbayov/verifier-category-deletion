"""
openrouter_client.py
---------------------
Minimal OpenRouter chat-completions client for candidate generation
(soundver_experiments.py's generate_candidates hook). Reads the API key
from OPENROUTER_API_KEY, set via the .env file in the parent directory --
never hardcode it and never print it.

Cost note: every call here spends real money against the user's OpenRouter
balance. Keep default sample sizes small until a pilot run is confirmed
sane; see run_spider_pilot.py for the guarded entry point.
"""

import os
import time
from pathlib import Path
import requests

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _load_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text().splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError(
        f"OPENROUTER_API_KEY not found in environment or {_ENV_PATH}")


_API_KEY = None


def _key():
    global _API_KEY
    if _API_KEY is None:
        _API_KEY = _load_api_key()
    return _API_KEY


MODEL_SLUGS = {
    "gpt-4o-mini": "openai/gpt-4o-mini",
    "gpt-4o": "openai/gpt-4o",
    "llama-3.1-8b": "meta-llama/llama-3.1-8b-instruct",
    "llama-3.1-70b": "meta-llama/llama-3.1-70b-instruct",
}

# OpenRouter is a multi-provider router: the same model slug can be served
# by different upstream backends across calls, and not all of them return
# logprobs (confirmed empirically -- meta-llama/llama-3.1-8b-instruct via
# DeepInfra/Groq/Cloudflare returns logprobs: null, while Novita and
# CoreWeave do). Pin a logprobs-supporting provider for the two Llama
# models used by the log-probability scorer (E5/E6); OpenAI's own models
# have been reliable across repeated calls and need no pin.
LOGPROB_PROVIDER = {
    "llama-3.1-8b": "Novita",
    "llama-3.1-70b": "CoreWeave",
}


def chat_completion(model: str, prompt: str, temperature: float = 0.0,
                     max_tokens: int = 512, retries: int = 3) -> str:
    """One completion. model is a key into MODEL_SLUGS or a raw OpenRouter slug."""
    slug = MODEL_SLUGS.get(model, model)
    headers = {"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"}
    payload = {
        "model": slug,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001 -- network/API errors, retry then surface
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"OpenRouter call failed after {retries} attempts: {last_err}")


def sample_candidates(model: str, prompt: str, n: int, temperature: float,
                       max_tokens: int = 512) -> list:
    """n i.i.d. samples at `temperature`. Use temperature=0.0 separately for
    the greedy base y0, since that's a distinct call, not one of these n."""
    return [chat_completion(model, prompt, temperature=temperature, max_tokens=max_tokens)
            for _ in range(n)]


def chat_completion_with_logprobs(model: str, prompt: str, temperature: float = 0.0,
                                   max_tokens: int = 512, retries: int = 3) -> dict:
    """Like chat_completion, but also returns the mean per-token log-
    probability of the completion, for the 'reject the highest-log-
    probability candidate' adversarial scorer (BLOCKERS.txt E5/E6 design,
    Sec. 6's baseline list). Returns {"text": str, "mean_logprob": float}.
    mean_logprob is None if the provider didn't return logprobs even after
    pinning (checked, not assumed): retries once more with no provider
    pin as a fallback, then gives up and returns None rather than silently
    treating a missing scorer value as zero."""
    slug = MODEL_SLUGS.get(model, model)
    headers = {"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"}
    payload = {
        "model": slug,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "logprobs": True,
    }
    if model in LOGPROB_PROVIDER:
        payload["provider"] = {"only": [LOGPROB_PROVIDER[model]]}
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            text = choice["message"]["content"]
            token_logprobs = None
            lp = choice.get("logprobs")
            if lp and lp.get("content"):
                token_logprobs = [t["logprob"] for t in lp["content"] if "logprob" in t]
            mean_logprob = (sum(token_logprobs) / len(token_logprobs)
                             if token_logprobs else None)
            return {"text": text, "mean_logprob": mean_logprob}
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"OpenRouter call failed after {retries} attempts: {last_err}")


def sample_candidates_with_logprobs(model: str, prompt: str, n: int, temperature: float,
                                     max_tokens: int = 512) -> list:
    """n i.i.d. samples at `temperature`, each with its mean log-probability."""
    return [chat_completion_with_logprobs(model, prompt, temperature=temperature,
                                           max_tokens=max_tokens)
            for _ in range(n)]


def estimate_cost_usd(model: str, n_calls: int, avg_input_tokens: int = 300,
                       avg_output_tokens: int = 150) -> float:
    """Rough cost estimate for budgeting before a real run. Prices are
    approximate OpenRouter per-1M-token rates as of the model's listing;
    re-check https://openrouter.ai/models before a real run since these
    drift and this function must not be trusted blindly."""
    per_1m = {
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4o": (2.50, 10.00),
        "llama-3.1-8b": (0.02, 0.05),
        "llama-3.1-70b": (0.12, 0.30),
    }
    in_rate, out_rate = per_1m.get(model, (1.0, 3.0))
    cost = n_calls * (avg_input_tokens / 1e6 * in_rate + avg_output_tokens / 1e6 * out_rate)
    return round(cost, 4)
