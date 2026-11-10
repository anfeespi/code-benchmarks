"""Build the v4-strict suite (tests/strict/<slug>.json) from codebench/strict/<category>.py.

Usage:
  python -m codebench.build_strict build <slug|category|all>   # cross-check + write + expected + canonical 100%
  python -m codebench.build_strict cross <slug|category>          # cross-check only (brute vs canonical)
  python -m codebench.build_strict flips <slug|category|all> [--jobs N]
        # score every data/outputs/code-bench-v4__*.json (not july) under v4 and strict for those
        # problems and list pass->fail flips with the failing cases
  python -m codebench.build_strict stats                          # cases per problem/category, v4 vs strict
"""
import argparse
import collections
import importlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from . import strict as kit
from .harness import ROOT, SUITES, load_problems, load_tests, build_expected, score_candidate, extract_code

CATEGORIES = ["algorithms", "bug_fixing", "data_structures", "edge_cases", "optimization", "spec_compliance"]
STRICT_DIR = SUITES["strict"]
OUT = ROOT / "data" / "outputs"


def _load_registry():
    for c in CATEGORIES:
        try:
            importlib.import_module("codebench.strict." + c)
        except ModuleNotFoundError as e:
            if e.name != "codebench.strict." + c:
                raise
    return kit.REGISTRY


def _select(probs, key):
    if key in ("all", "--all"):
        return probs
    return [p for p in probs if p["slug"] == key or p["category"] == key]


def canonical_ns(problem):
    ns = {"__name__": "canonical_" + problem["slug"].replace("-", "_")}
    exec(compile(problem["canonical_solution"], "<canonical>", "exec"), ns)
    return ns


def cross_check(problem, spec):
    ns = canonical_ns(problem)
    canon = ns[problem["entry_point"]]
    n = getattr(spec, "n_cross", 500)
    with_msg = getattr(spec, "cross_msg", False)
    call = getattr(spec, "call", None)
    call = call if call is None else (lambda fn, args, _c=call: _c(fn, args))
    rng = kit.rng_for(problem["slug"], 1)
    mismatches = []
    for i in range(n):
        args = spec.gen(rng)
        a = kit.outcome(canon, args, call, with_msg)
        b = kit.outcome(spec.brute, args, call, with_msg)
        if not (a == b):
            mismatches.append({"i": i, "args": repr(args)[:400], "canonical": repr(a)[:300], "brute": repr(b)[:300]})
    return {"n": n, "agree": n - len(mismatches), "reference": getattr(spec, "note", "")}, mismatches


def build(problem, spec, verbose=True):
    stats, mism = cross_check(problem, spec)
    if mism:
        print("CROSS-CHECK MISMATCH %s: %d/%d" % (problem["slug"], len(mism), stats["n"]))
        for m in mism[:5]:
            print("   ", json.dumps(m)[:900])
        raise SystemExit(1)
    v4 = load_tests(problem["slug"], "v4")
    cases = [dict(c, name="v4:" + c["name"]) for c in v4["cases"]]
    for c in cases:
        c.pop("expected", None)
        c.pop("raises", None)
    new = spec.cases(kit.rng_for(problem["slug"], 2))
    names = [c["name"] for c in cases + new]
    dup = [k for k, v in collections.Counter(names).items() if v > 1]
    if dup:
        raise SystemExit("duplicate case names in %s: %s" % (problem["slug"], dup))
    tests = {"title": problem["title"], "entry_point": problem["entry_point"], "suite": "v4-strict",
             "crosscheck": stats, "cases": cases + new}
    build_expected(problem, tests)
    s = score_candidate(problem, problem["canonical_solution"], tests)
    if not s["pass"]:
        raise SystemExit("canonical fails its strict tests in %s: %s" % (problem["slug"], s["detail"][:5]))
    STRICT_DIR.mkdir(parents=True, exist_ok=True)
    (STRICT_DIR / (problem["slug"] + ".json")).write_text(json.dumps(tests, indent=1, ensure_ascii=False))
    if verbose:
        print("%-62s cross %d/%d  cases v4=%d strict=%d (+%d)  canonical pass" % (
            problem["slug"], stats["agree"], stats["n"], len(v4["cases"]), len(tests["cases"]), len(new)))
    return tests


def v4_output_files():
    return sorted(p for p in OUT.glob("code-bench-v4__*.json"))


def flips(selected, jobs=8, verbose=True):
    sel = {p["title"]: p for p in selected}
    jobs_list = []
    for f in v4_output_files():
        model = f.stem.split("__", 1)[1]
        for r in json.load(open(f)):
            p = sel.get(r["title"])
            if p is None:
                continue
            code = r["code"] if isinstance(r["code"], str) else extract_code(str(r["code"] or ""))
            jobs_list.append((model, p, code))

    def run(job):
        model, p, code = job
        a = score_candidate(p, code, load_tests(p["slug"], "v4"))
        b = score_candidate(p, code, load_tests(p["slug"], "strict"))
        return model, p["slug"], a, b

    with ThreadPoolExecutor(max_workers=jobs) as ex:
        res = list(ex.map(run, jobs_list))
    rows = []
    for model, slug, a, b in res:
        row = {"model": model, "slug": slug, "v4": a["pass"], "strict": b["pass"], "strict_detail": b["detail"]}
        rows.append(row)
        if verbose and a["pass"] and not b["pass"]:
            print("FLIP %-20s %-58s" % (model, slug))
            for d in b["detail"][:4]:
                print("      ", d[:400])
        elif verbose and not a["pass"] and b["pass"]:
            print("ODD (fail v4, pass strict) %s %s" % (model, slug))
    if verbose:
        per = collections.defaultdict(lambda: [0, 0, 0])
        for r in rows:
            per[r["model"]][0] += r["v4"]
            per[r["model"]][1] += r["strict"]
            per[r["model"]][2] += 1
        print("%-22s %8s %10s %4s" % ("model", "pass v4", "pass strict", "n"))
        for m, (a_, b_, n) in sorted(per.items(), key=lambda kv: (-kv[1][1], kv[0])):
            print("%-22s %8d %10d %4d" % (m, a_, b_, n))
    return rows


def stats():
    probs = load_problems()
    per_cat = collections.defaultdict(lambda: [0, 0])
    for p in probs:
        a = load_tests(p["slug"], "v4")
        b = load_tests(p["slug"], "strict")
        na, nb = len(a["cases"]), len(b["cases"]) if b else 0
        per_cat[p["category"]][0] += na
        per_cat[p["category"]][1] += nb
        print("%-16s %-62s v4=%-3d strict=%s" % (p["category"], p["slug"], na, nb if b else "-"))
    for c, (a, b) in sorted(per_cat.items()):
        print("%-16s v4=%d strict=%d" % (c, a, b))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "cross", "flips", "stats"])
    ap.add_argument("key", nargs="?", default="all", help="slug, category or all (default)")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--json", help="flips: write per-(model, problem) rows here")
    a = ap.parse_args(argv)
    if a.cmd == "stats":
        return stats()
    reg = _load_registry()
    probs = _select(load_problems(), a.key)
    if a.cmd == "flips":
        rows = flips(probs, a.jobs)
        if a.json:
            open(a.json, "w").write(json.dumps(rows, indent=1))
        return
    for p in probs:
        spec = reg.get(p["slug"])
        if spec is None:
            print("no strict spec:", p["slug"])
            continue
        if a.cmd == "cross":
            st, mism = cross_check(p, spec)
            print(p["slug"], st)
            for m in mism[:5]:
                print("   ", json.dumps(m)[:900])
        else:
            build(p, spec)


if __name__ == "__main__":
    main(sys.argv[1:])
