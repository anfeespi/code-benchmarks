"""Score an outputs file under the local test suite and summarise it.

Usage:
  python -m codebench.score data/outputs/code-bench-v4__fable-5.1.json [--write] [--verbose]
  python -m codebench.score --all-v3            # re-score the five stored July v3 runs (the v4 baseline)
  python -m codebench.score data/outputs/code-bench-v4__*.json --tests strict   # v4-strict suite
--tests picks the suite: v4 (default, tests/<slug>.json) or strict (tests/strict/<slug>.json).
--jobs N scores N problems concurrently (default 1).
--write stores the new scores back into the file under "scores" (keeping any stored July
scores under "scores_july").
"""
import argparse
import collections
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .harness import ROOT, load_problems, load_tests, score_candidate, extract_code

OUT = ROOT / "data" / "outputs"


def score_file(path, write=False, verbose=False, suite="v4", jobs=1):
    probs = {p["title"]: p for p in load_problems()}
    rows = json.load(open(path))

    def _score(r):
        p = probs[r["title"]]
        code = r["code"] if isinstance(r["code"], str) else extract_code(str(r["code"] or ""))
        return score_candidate(p, code, load_tests(p["slug"], suite))

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        scored = list(ex.map(_score, rows))
    by_cat = collections.defaultdict(lambda: [0, 0, 0])  # pass, refused, n
    tot = {"pass": 0, "ratio": 0.0, "checker": 0, "refused": 0, "attempted": 0, "n": 0}
    for r, s in zip(rows, scored):
        p = probs[r["title"]]
        code = r["code"] if isinstance(r["code"], str) else extract_code(str(r["code"] or ""))
        refused = bool((r.get("metadata") or {}).get("refused")) or (r.get("metadata") or {}).get("empty_output") is True and not code.strip()
        if write and suite != "v4":
            r.setdefault("scores_by_suite", {})[suite] = {"checker": s["checker"], "tests_ratio": s["tests_ratio"], "pass": s["pass"]}
            r.setdefault("detail_by_suite", {})[suite] = s["detail"]
        elif write:
            if r.get("scores") and "scores_july" not in r:
                r["scores_july"] = r["scores"]
            r["scores"] = {"checker": s["checker"], "tests_ratio": s["tests_ratio"], "pass": s["pass"]}
            r["detail"] = s["detail"]
        by_cat[p["category"]][2] += 1
        by_cat[p["category"]][0] += s["pass"]
        by_cat[p["category"]][1] += int(refused)
        tot["n"] += 1; tot["pass"] += s["pass"]; tot["ratio"] += s["tests_ratio"]; tot["checker"] += s["checker"]
        tot["refused"] += int(refused); tot["attempted"] += int(not refused)
        if verbose and not s["pass"]:
            print("  FAIL %-16s %-55s %s" % (p["category"], p["slug"], "REFUSED" if refused else "; ".join(s["detail"][:2])[:160]))
    if write:
        Path(path).write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    att = tot["attempted"]
    print("[%s] %s: pass %d/%d (%.0f%% raw, %.0f%% when attempted) | tests_ratio %.3f | checker %.3f | refused %d" % (
        suite, Path(path).name, tot["pass"], tot["n"], 100 * tot["pass"] / tot["n"], 100 * tot["pass"] / att if att else 0,
        tot["ratio"] / tot["n"], tot["checker"] / tot["n"], tot["refused"]))
    for c, (p_, rf, n) in sorted(by_cat.items()):
        print("   %-16s %d/%d%s" % (c, p_, n, "  (refused %d)" % rf if rf else ""))
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all-v3", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--tests", choices=["v4", "strict"], default="v4", help="test suite (default v4)")
    ap.add_argument("--jobs", type=int, default=1)
    a = ap.parse_args()
    files = list(a.files)
    if a.all_v3:
        files += sorted(str(p) for p in OUT.glob("code-bench-v3__*.json"))
    for f in files:
        score_file(f, a.write, a.verbose, suite=a.tests, jobs=a.jobs)


if __name__ == "__main__":
    main()
