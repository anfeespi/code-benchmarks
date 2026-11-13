"""Generate and grade one model on the hard suite in several languages.

Usage:
  python -m codebench.multilang.bench --provider openrouter --model <id> --tag <tag> \
      --key-file <file> [--langs python go cpp typescript] [--only slug ...] [--jobs 4]
  python -m codebench.multilang.bench --table            # pass counts per model and language

Output: data/multilang/outputs/hard-v1__<tag>.json, one row per (problem, language). Answers
are cached in data/multilang/runs/<tag>/ so a rerun only regrades.
"""
import argparse
import collections
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import generate, harness
from . import langs, run, typesys

OUT = harness.ROOT / "data" / "multilang" / "outputs"
RUNS = harness.ROOT / "data" / "multilang" / "runs"


def ask(a, key, session, text):
    if a.provider == "openrouter":
        return generate.call_openrouter(a.model, text, key)
    if a.provider == "anthropic":
        return generate.call_anthropic(a.model, text, key)
    if a.provider == "google":
        return generate.call_google(a.model, text, key)
    return generate.call_bedrock(a.model, text, session)


def one(a, key, session, problem, lang):
    sig = run.load_neutral(problem)["signature"]
    row = {"slug": problem["slug"], "category": problem["category"], "lang": lang}
    if not langs.supported(lang, sig):
        return dict(row, supported=False)
    cache = RUNS / a.tag / ("%s__%s.json" % (problem["slug"], lang))
    if cache.exists():
        resp = json.loads(cache.read_text())
    else:
        resp = ask(a, key, session, langs.prompt(lang, problem, sig))
        if "error" not in resp:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(resp))
    if "error" in resp:
        return dict(row, supported=True, error=resp["error"], **{"pass": 0})
    code = langs.extract_code(lang, resp.get("text"))
    truncated = resp.get("stop_reason") in ("length", "max_tokens")
    refused = resp.get("stop_reason") == "refusal" or not code.strip()
    res = run.score(lang, problem, code) if code.strip() else {"pass": 0, "passed": 0, "n_cases": 0, "detail": ["empty answer"]}
    return dict(row, supported=True, code=code, refused=refused and not truncated, truncated=truncated,
                tokens_out=resp.get("tokens_out"), cost_usd=resp.get("cost_usd"), latency_s=resp.get("latency_s"),
                **{k: res.get(k) for k in ("pass", "passed", "n_cases", "n_skipped", "detail")})


def table():
    files = sorted(OUT.glob("hard-v1__*.json"))
    print("%-24s %s" % ("model", "  ".join("%-12s" % l for l in langs.LANGS)))
    for f in files:
        rows = [r for r in json.loads(f.read_text()) if r.get("supported")]
        cells = []
        for l in langs.LANGS:
            mine = [r for r in rows if r["lang"] == l]
            cells.append("%-12s" % ("%d/%d" % (sum(r["pass"] for r in mine), len(mine)) if mine else "-"))
        print("%-24s %s" % (f.stem[len("hard-v1__"):], "  ".join(cells)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["anthropic", "openrouter", "bedrock", "google"])
    ap.add_argument("--model")
    ap.add_argument("--tag")
    ap.add_argument("--key-file")
    ap.add_argument("--aws-profile")
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--langs", nargs="*", default=list(langs.LANGS))
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--table", action="store_true")
    a = ap.parse_args()
    if a.table:
        return table()
    harness.use_suite("hard-v1")
    if "CODEBENCH_MAX_TOKENS" not in os.environ:
        generate.MAX_TOKENS = generate.HARD_MAX_TOKENS
    key = Path(a.key_file).read_text().strip() if a.key_file else None
    session = None
    if a.provider == "bedrock":
        import boto3
        session = boto3.Session(profile_name=a.aws_profile, region_name=a.region)
    problems = [p for p in harness.load_problems() if not a.only or p["slug"] in a.only]
    for p in problems:
        run.load_neutral(p)
    jobs = [(p, l) for p in problems for l in a.langs]
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        rows = list(ex.map(lambda j: one(a, key, session, *j), jobs))
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / ("hard-v1__%s.json" % a.tag)
    # A partial rerun (one language, a few problems) replaces only the rows it produced.
    fresh = {(r["slug"], r["lang"]) for r in rows}
    kept = [r for r in json.loads(out.read_text()) if (r["slug"], r["lang"]) not in fresh] if out.exists() else []
    out.write_text(json.dumps(kept + rows, indent=1, ensure_ascii=False))
    by = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        if not r.get("supported"):
            continue
        by[r["lang"]][0] += r["pass"]
        by[r["lang"]][1] += 1
        if not r["pass"]:
            print("  FAIL %-11s %-34s %s" % (r["lang"], r["slug"], r.get("error") or "; ".join((r.get("detail") or [])[:1])[:150]))
    print("[%s] " % a.tag + " | ".join("%s %d/%d" % (l, by[l][0], by[l][1]) for l in a.langs if by[l][1]))
    print("cost $%.2f" % sum((r.get("cost_usd") or 0) for r in rows))


if __name__ == "__main__":
    main()
