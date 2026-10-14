"""Authoring + validation tools for the hard tier (suite "hard-v1").

Source of truth per problem lives in data/problems/hard-refs/<slug>/:
  meta.json      {"id": "hard-<slug>", "title": ..., "category": ..., "entry_point": ...}
  prompt.md      the prompt shown to the model (verbatim)
  canonical.py   the canonical solution (efficient)
  brute.py       independent brute-force reference (slow, obviously correct), same entry point
  gen.py         random small-input generator for the cross-check:
                   gen(rng) -> tuple of positional args
                   optional call(mod, args) -> value   (default: getattr(mod, entry_point)(*args))
                   optional N = <int>                   (number of cases, default 500)
  naive.py       (performance problems) a correct but slow solution that must fail the stress cases
Tests live in tests/hard/<slug>.json (harness format; stress cases are named "stress_*").

Usage:
  python -m codebench.hard_tools assemble                  # hard-refs/* -> data/problems/code-bench-hard-v1.json
  python -m codebench.hard_tools build <slug>... | --all   # assemble + fill expected from canonical + canonical self-check
  python -m codebench.hard_tools crosscheck <slug>... | --all [--n 500]
  python -m codebench.hard_tools naive <slug>... | --all   # naive.py must pass non-stress cases and fail stress ones
  python -m codebench.hard_tools selfcheck                 # canonical vs every test through the harness
  python -m codebench.hard_tools timing <slug>... | --all  # canonical wall time on stress cases vs timeout_s
Results of crosscheck / naive / selfcheck / timing are recorded in data/problems/hard-refs/_results/<kind>/<slug>.json.
"""
import copy
import importlib.util
import json
import math
import os
import random
import sys
import time
import traceback
from pathlib import Path

from . import harness

REFS = harness.ROOT / "data" / "problems" / "hard-refs"
RESULTS = REFS / "_results"
harness.use_suite("hard-v1")


def _atomic_write(path, text):
    tmp = Path(str(path) + ".tmp%d" % os.getpid())
    tmp.write_text(text)
    os.replace(tmp, path)


def slugs_all():
    return sorted(d.name for d in REFS.iterdir() if d.is_dir() and not d.name.startswith("_") and all((d / f).exists() for f in ("meta.json", "prompt.md", "canonical.py")))


def load_src(slug):
    d = REFS / slug
    meta = json.load(open(d / "meta.json"))
    return {"id": meta["id"], "title": meta["title"], "category": meta["category"],
            "n_tests": None, "entry_point": meta["entry_point"],
            "prompt": (d / "prompt.md").read_text(), "canonical_solution": (d / "canonical.py").read_text()}


CATEGORY_ORDER = ["algorithms", "state_machines", "spec_compliance", "parsing", "performance", "numeric",
                  "data_structures", "bug_fixing"]


def assemble():
    probs = []
    for s in slugs_all():
        try:
            p = load_src(s)
            t = harness.load_tests(s)
        except Exception as e:  # a dir being authored concurrently; skip it this time
            print("assemble: skipping %s (%s)" % (s, e))
            continue
        assert p["id"] == "hard-" + s, (p["id"], s)
        p["n_tests"] = len(t["cases"]) if t else 0
        probs.append(p)
    probs.sort(key=lambda p: (CATEGORY_ORDER.index(p["category"]) if p["category"] in CATEGORY_ORDER else 99, p["id"]))
    _atomic_write(harness.PROBLEMS, json.dumps(probs, indent=1, ensure_ascii=False) + "\n")
    print("assembled %d problems -> %s" % (len(probs), harness.PROBLEMS.relative_to(harness.ROOT)))
    return probs


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _run(gen, mod, entry, args):
    try:
        if hasattr(gen, "call"):
            v = gen.call(mod, copy.deepcopy(args))
        else:
            v = getattr(mod, entry)(*copy.deepcopy(args))
        return ("ok", v)
    except Exception as e:  # compare type + message: messages are part of several contracts
        return ("exc", type(e).__name__, str(e))


def _same(a, b):
    if a[0] != b[0]:
        return False
    if a[0] == "exc":
        return a[1:] == b[1:]
    return _eq(a[1], b[1])


def _eq(x, y):
    if isinstance(x, float) and isinstance(y, float):
        return (math.isnan(x) and math.isnan(y)) or x == y
    if type(x) is not type(y) and not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
        return False
    if isinstance(x, (list, tuple)):
        return len(x) == len(y) and all(_eq(a, b) for a, b in zip(x, y))
    if isinstance(x, dict):
        return list(x.keys()) == list(y.keys()) and all(_eq(x[k], y[k]) for k in x)
    return x == y


def crosscheck(slug, n=None):
    d = REFS / slug
    meta = json.load(open(d / "meta.json"))
    if not (d / "brute.py").exists():
        return {"slug": slug, "status": "no-brute"}
    gen = _mod(d / "gen.py", "gen_" + slug.replace("-", "_"))
    can = _mod(d / "canonical.py", "can_" + slug.replace("-", "_"))
    bru = _mod(d / "brute.py", "bru_" + slug.replace("-", "_"))
    n = n or getattr(gen, "N", 500)
    agree, mism, kinds = 0, [], {"ok": 0, "exc": 0}
    t0 = time.time()
    for i in range(n):
        rng = random.Random(1_000_003 * (i + 1) + 17)
        args = gen.gen(rng)
        a = _run(gen, can, meta["entry_point"], args)
        b = _run(gen, bru, meta["entry_point"], args)
        if _same(a, b):
            agree += 1
            kinds[a[0]] += 1
        elif len(mism) < 5:
            mism.append({"seed_index": i, "args": repr(args)[:400], "canonical": repr(a)[:300], "brute": repr(b)[:300]})
    res = {"slug": slug, "n": n, "agree": agree, "status": "ok" if agree == n else "MISMATCH",
           "outcomes": kinds, "seconds": round(time.time() - t0, 2), "mismatches": mism}
    return res


def naive(slug):
    d = REFS / slug
    if not (d / "naive.py").exists():
        return {"slug": slug, "status": "no-naive"}
    probs = {p["slug"]: p for p in harness.load_problems()}
    p = probs[slug]
    t = harness.load_tests(slug)
    s = harness.score_candidate(p, (d / "naive.py").read_text(), t)
    stress = [c["name"] for c in t["cases"] if c["name"].startswith("stress")]
    failed = {x.split(":")[0] for x in s["detail"]}
    res = {"slug": slug, "stress_cases": len(stress), "stress_failed": sum(1 for c in stress if c in failed),
           "nonstress_failed": sorted(failed - set(stress)), "naive_pass": s["pass"]}
    res["status"] = "ok" if res["stress_failed"] >= 1 and not res["nonstress_failed"] else "BAD"
    return res


def timing(slug):
    probs = {p["slug"]: p for p in harness.load_problems()}
    p = probs[slug]
    t = harness.load_tests(slug)
    sol = harness._write_sol(p["canonical_solution"])
    out = []
    for c in t["cases"]:
        if not c["name"].startswith("stress"):
            continue
        t0 = time.time()
        r = harness.run_case(sol, p["entry_point"], c["code"], c.get("timeout_s", harness.DEFAULT_TIMEOUT))
        dt = time.time() - t0
        out.append({"case": c["name"], "seconds": round(dt, 3), "timeout_s": c.get("timeout_s", harness.DEFAULT_TIMEOUT),
                    "margin": round(c.get("timeout_s", harness.DEFAULT_TIMEOUT) / dt, 1), "ok": bool(r.get("ok") or r.get("exc"))})
    return {"slug": slug, "cases": out, "min_margin": min((o["margin"] for o in out), default=None)}


def selfcheck():
    tot = passed = 0
    rows = []
    for p in harness.load_problems():
        t = harness.load_tests(p["slug"])
        s = harness.score_candidate(p, p["canonical_solution"], t)
        tot += 1
        passed += s["pass"]
        rows.append({"slug": p["slug"], "cases": len(t["cases"]), "pass": s["pass"], "detail": s["detail"][:3]})
        print("%-16s %-48s cases=%-3d pass=%s %s" % (p["category"], p["slug"], len(t["cases"]), s["pass"], "; ".join(s["detail"][:2])[:200]))
    print("canonical self-check: %d/%d problems pass all their tests" % (passed, tot))
    return {"passed": passed, "total": tot, "rows": rows}


def _save(kind, obj):
    """One file per (kind, slug) so parallel authoring runs never clobber each other."""
    d = RESULTS / kind
    d.mkdir(parents=True, exist_ok=True)
    name = obj["slug"] if isinstance(obj, dict) and "slug" in obj else "_all"
    _atomic_write(d / (name + ".json"), json.dumps(obj, indent=1, ensure_ascii=False, default=repr) + "\n")


def main(argv):
    cmd = argv[0] if argv else "help"
    rest = argv[1:]
    n = None
    if "--n" in rest:
        i = rest.index("--n")
        n = int(rest[i + 1])
        rest = rest[:i] + rest[i + 2:]
    slugs = slugs_all() if "--all" in rest else rest
    if cmd == "assemble":
        assemble()
    elif cmd == "build":
        assemble()
        probs = {p["slug"]: p for p in harness.load_problems()}
        for s in slugs:
            t = harness.load_tests(s)
            if t is None:
                print("no tests:", s)
                continue
            try:
                harness.build_expected(probs[s], t)
            except Exception as e:
                print("BUILD FAILED %s: %s" % (s, e))
                continue
            (harness.TESTS_DIR / (s + ".json")).write_text(json.dumps(t, indent=1, ensure_ascii=False) + "\n")
            sc = harness.score_candidate(probs[s], probs[s]["canonical_solution"], t)
            print("%-48s cases=%-3d canonical pass=%s %s" % (s, len(t["cases"]), sc["pass"], "; ".join(sc["detail"][:2])[:200]))
        assemble()
    elif cmd == "crosscheck":
        for s in slugs:
            try:
                r = crosscheck(s, n)
            except Exception:
                r = {"slug": s, "status": "ERROR", "trace": traceback.format_exc()[-800:]}
            print("%-48s %s %s/%s %s" % (s, r["status"], r.get("agree"), r.get("n"), json.dumps(r.get("mismatches") or r.get("trace") or "")[:600]))
            _save("crosscheck", r)
    elif cmd == "naive":
        for s in slugs:
            r = naive(s)
            print("%-48s %s %s" % (s, r["status"], json.dumps({k: v for k, v in r.items() if k not in ("slug", "status")})))
            if r["status"] != "no-naive":
                _save("naive", r)
    elif cmd == "timing":
        for s in slugs:
            r = timing(s)
            print("%-48s min_margin=%s %s" % (s, r["min_margin"], json.dumps(r["cases"])))
            if r["cases"]:
                _save("timing", r)
    elif cmd == "selfcheck":
        _save("selfcheck", selfcheck())
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
