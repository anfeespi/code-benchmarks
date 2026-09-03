"""Generate candidate solutions for the 48 problems with one model.

Same protocol as the July runs: the problem prompt is the only user message, no system
prompt; Claude models get no temperature (deprecated on Claude 5), OpenRouter models run
at temperature 0. Refusals are recorded explicitly (stop_reason == "refusal" or an empty
answer) so they are never confused with wrong answers.

Usage:
  python -m codebench.generate --provider anthropic  --model claude-fable-5-1 --tag fable-5.1
  python -m codebench.generate --provider openrouter --model google/gemini-3.8-flash --tag gemini-3.8-flash
Keys: ANTHROPIC_API_KEY / OPENROUTER_API_KEY from the environment, or --key-file.
Output: data/outputs/code-bench-v4__<tag>.json (same shape as the stored July files) and a
resumable per-problem cache in data/runs/<tag>/.
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from .harness import ROOT, load_problems, extract_code

MAX_TOKENS = int(os.environ.get("CODEBENCH_MAX_TOKENS", "16384"))


def _post(url, headers, body, timeout=600):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=dict(headers, **{"Content-Type": "application/json"}))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except Exception:
            return e.code, {"error": e.read()[:500].decode(errors="replace")}


def call_anthropic(model, prompt, key):
    body = {"model": model, "max_tokens": MAX_TOKENS, "messages": [{"role": "user", "content": prompt}]}
    t0 = time.time()
    status, resp = _post("https://api.anthropic.com/v1/messages",
                         {"x-api-key": key, "anthropic-version": "2023-06-01"}, body)
    lat = time.time() - t0
    if status != 200:
        return {"error": "%s %s" % (status, json.dumps(resp)[:300]), "latency_s": lat}
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    usage = resp.get("usage", {})
    return {"text": text, "stop_reason": resp.get("stop_reason"), "latency_s": lat,
            "tokens_in": usage.get("input_tokens"), "tokens_out": usage.get("output_tokens"), "cost_usd": None}


def call_openrouter(model, prompt, key):
    body = {"model": model, "temperature": 0, "max_tokens": MAX_TOKENS, "messages": [{"role": "user", "content": prompt}],
            "usage": {"include": True}}
    t0 = time.time()
    status, resp = _post("https://openrouter.ai/api/v1/chat/completions",
                         {"Authorization": "Bearer " + key, "HTTP-Referer": "https://y.uno", "X-Title": "code-bench"}, body)
    lat = time.time() - t0
    if status != 200 or "choices" not in resp:
        return {"error": "%s %s" % (status, json.dumps(resp)[:300]), "latency_s": lat}
    ch = resp["choices"][0]
    usage = resp.get("usage", {})
    return {"text": ch.get("message", {}).get("content") or "", "stop_reason": ch.get("finish_reason"), "latency_s": lat,
            "tokens_in": usage.get("prompt_tokens"), "tokens_out": usage.get("completion_tokens"), "cost_usd": usage.get("cost")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["anthropic", "openrouter"], required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", required=True, help="suffix for data/outputs/code-bench-v4__<tag>.json")
    ap.add_argument("--key-file")
    ap.add_argument("--only", nargs="*", help="slugs to (re)generate")
    ap.add_argument("--retries", type=int, default=2)
    a = ap.parse_args()
    env = "ANTHROPIC_API_KEY" if a.provider == "anthropic" else "OPENROUTER_API_KEY"
    key = open(a.key_file).read().strip() if a.key_file else os.environ.get(env)
    if not key:
        raise SystemExit("missing %s (or --key-file)" % env)
    call = call_anthropic if a.provider == "anthropic" else call_openrouter
    cache = ROOT / "data" / "runs" / a.tag
    cache.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in load_problems():
        cf = cache / (p["slug"] + ".json")
        if cf.exists() and not (a.only and p["slug"] in a.only):
            r = json.load(open(cf))
        else:
            r = None
            for attempt in range(a.retries + 1):
                r = call(a.model, p["prompt"], key)
                if "error" not in r:
                    break
                time.sleep(3 * (attempt + 1))
            r["slug"] = p["slug"]
            json.dump(r, open(cf, "w"), indent=1)
        text = r.get("text") or ""
        refused = (r.get("stop_reason") == "refusal") or (not text.strip() and "error" not in r)
        code = "" if refused else extract_code(text)
        rows.append({"title": p["title"], "category": p["category"], "entry_point": p["entry_point"], "code": code,
                     "scores": None,
                     "metadata": {"category": p["category"], "title": p["title"], "model": a.model, "provider": a.provider,
                                  "latency_s": round(r.get("latency_s") or 0, 2), "tokens_in": r.get("tokens_in"),
                                  "tokens_out": r.get("tokens_out"), "cost_usd": r.get("cost_usd"),
                                  "stop_reason": r.get("stop_reason"), "refused": bool(refused),
                                  "empty_output": not bool(code.strip()), "error": r.get("error")}})
        print("%-16s %-58s %s%s" % (p["category"], p["slug"], "REFUSED" if refused else ("ERROR" if r.get("error") else "ok"),
                                    "" if not r.get("error") else " " + r["error"][:80]))
    out = ROOT / "data" / "outputs" / ("code-bench-v4__%s.json" % a.tag)
    json.dump(rows, open(out, "w"), indent=1, ensure_ascii=False)
    n_ref = sum(1 for r in rows if r["metadata"]["refused"]); n_err = sum(1 for r in rows if r["metadata"]["error"])
    print("wrote", out, "| refused", n_ref, "| errors", n_err)


if __name__ == "__main__":
    main()
