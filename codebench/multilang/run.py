"""Score one candidate in one language against the recorded calls of a problem.

Usage:
  python -m codebench.multilang.run selfcheck            # canonical Python passes every neutral case
  python -m codebench.multilang.run file <lang> <slug> <solution file> [-v]
"""
import json
import math
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .. import harness
from . import langs, materialize, typesys

# Process start is part of every measured case, so slow-starting runtimes get it back.
STARTUP_ALLOWANCE = {"python": 0.3, "typescript": 0.5, "go": 0.1, "cpp": 0.1, "java": 0.8}


def same(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if isinstance(a, int) and isinstance(b, int):
            return a == b
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        if "__pairs__" in a and "__pairs__" in b:
            ka = sorted(a["__pairs__"], key=lambda p: json.dumps(p[0]))
            kb = sorted(b["__pairs__"], key=lambda p: json.dumps(p[0]))
            return same(ka, kb)
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    return a == b


def load_neutral(problem):
    path = materialize.CACHE / (problem["slug"] + ".json")
    if not path.exists():
        materialize.main(["build", problem["slug"]])
    return json.loads(path.read_text())


def score(lang, problem, code, verbose=False):
    doc = load_neutral(problem)
    sig = doc["signature"]
    if not langs.supported(lang, sig):
        return {"supported": False}
    cases = [c for c in doc["cases"] if langs.portable_case(lang, c)]
    out = {"supported": True, "n_cases": len(cases), "n_skipped": len(doc["cases"]) - len(cases),
           "passed": 0, "detail": [], "pass": 0}
    with tempfile.TemporaryDirectory(prefix="mlang-") as work:
        argv, err = langs.build(lang, problem, sig, code, work)
        if err:
            out["detail"].append(err)
            return out
        for i, case in enumerate(cases):
            cf = Path(work) / ("case_%d.json" % i)
            cf.write_text(json.dumps({"entry_point": problem["entry_point"],
                                      "entry_name": langs.entry_name(lang, problem["entry_point"]),
                                      "signature": sig, "calls": [{"args": k["args"]} for k in case["calls"]]}))
            limit = (case["timeout_s"] or harness.DEFAULT_TIMEOUT) + STARTUP_ALLOWANCE[lang]
            t0 = time.time()
            try:
                p = subprocess.run([a.replace("{case}", str(cf)) for a in argv], cwd=work,
                                   capture_output=True, text=True, timeout=limit)
                took = time.time() - t0
                got = json.loads(p.stdout)["results"]
                bad = next((j for j, (k, g) in enumerate(zip(case["calls"], got))
                            if (("error" in k) != bool(g.get("error")))
                            or ("error" not in k and not same(k["value"], g.get("value")))), None)
                if len(got) != len(case["calls"]):
                    bad = len(got)
                verdict = None if bad is None else "wrong answer at call %d" % bad
            except subprocess.TimeoutExpired:
                took, verdict = limit, "timeout after %.1fs" % limit
            except Exception:
                took = time.time() - t0
                verdict = "crash: " + ((p.stderr or "").strip().splitlines() or ["no output"])[-1][:200]
            if verdict is None:
                out["passed"] += 1
            else:
                out["detail"].append("%s: %s" % (case["name"], verdict))
            if verbose:
                print("    %-40s %-6s %.2fs %s" % (case["name"], "ok" if verdict is None else "FAIL", took, verdict or ""))
    out["pass"] = int(out["n_cases"] > 0 and out["passed"] == out["n_cases"])
    return out


def main(argv=None):
    argv = argv or sys.argv[1:]
    harness.use_suite("hard-v1")
    problems = {p["slug"]: p for p in harness.load_problems()}
    if argv[0] == "selfcheck":
        bad = 0
        for slug, p in problems.items():
            r = score("python", p, p["canonical_solution"])
            ok = r["pass"] == 1
            bad += not ok
            print("%-4s %-36s %d/%d %s" % ("ok" if ok else "FAIL", slug, r["passed"], r["n_cases"], "; ".join(r["detail"][:2])))
        sys.exit(1 if bad else 0)
    _, lang, slug, path = argv[:4]
    r = score(lang, problems[slug], Path(path).read_text(), verbose="-v" in argv)
    print(json.dumps({k: v for k, v in r.items() if k != "detail"}), *r.get("detail", [])[:5], sep="\n")


if __name__ == "__main__":
    main()
