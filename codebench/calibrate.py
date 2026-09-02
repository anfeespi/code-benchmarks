"""Re-score stored model outputs under the local tests and compare with the stored
Braintrust scores (the July runs). Agreement on `pass` per (model, problem) is the
calibration target: disagreements point at over-strict or too-lenient tests.

Usage:
  python -m codebench.calibrate                      # all v3 experiments, all problems with tests
  python -m codebench.calibrate --category algorithms --verbose
  python -m codebench.calibrate --experiments code-bench-v3__kimi-k3 --slug peak-load
"""
import argparse
import json
from pathlib import Path

from .harness import ROOT, load_problems, load_tests, score_candidate, extract_code

OUT = ROOT / "data" / "outputs"
DEFAULT_EXPS = ["code-bench-v3__kimi-k3", "code-bench-v3__grok-4.5", "code-bench-v3__glm-5.2",
                "code-bench-v3__opus-5", "code-bench-v3__fable-5"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiments", nargs="*", default=DEFAULT_EXPS)
    ap.add_argument("--category")
    ap.add_argument("--slug")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--json", help="write per-row results here")
    a = ap.parse_args()
    probs = {p["title"]: p for p in load_problems()}
    rows, agree, total, missing = [], 0, 0, set()
    for exp in a.experiments:
        data = json.load(open(OUT / (exp + ".json")))
        for r in data:
            p = probs.get(r["title"])
            if p is None or (a.category and p["category"] != a.category) or (a.slug and p["slug"] != a.slug):
                continue
            tests = load_tests(p["slug"])
            if tests is None:
                missing.add(p["slug"])
                continue
            code = r["code"] if isinstance(r["code"], str) else extract_code(str(r["code"] or ""))
            got = score_candidate(p, code, tests)
            stored = r["scores"] or {}
            same = int(got["pass"]) == int(stored.get("pass", 0))
            agree += same
            total += 1
            rows.append({"experiment": exp, "slug": p["slug"], "category": p["category"], "stored_pass": stored.get("pass"),
                         "stored_ratio": stored.get("tests_ratio"), "pass": got["pass"], "tests_ratio": got["tests_ratio"],
                         "checker": got["checker"], "agree": same, "detail": got["detail"]})
            if a.verbose and not same:
                print("DISAGREE %-28s %-45s stored pass=%s ratio=%s | ours pass=%s ratio=%s" % (
                    exp, p["slug"], stored.get("pass"), stored.get("tests_ratio"), got["pass"], got["tests_ratio"]))
                for d in got["detail"][:6]:
                    print("      ", d)
    print("agreement on pass: %d/%d = %.1f%%" % (agree, total, 100.0 * agree / total if total else 0))
    if missing:
        print("problems without tests (%d): %s" % (len(missing), ", ".join(sorted(missing))))
    per = {}
    for r in rows:
        k = r["slug"]
        per.setdefault(k, [0, 0])
        per[k][0] += r["agree"]
        per[k][1] += 1
    bad = sorted((v[0] / v[1], k) for k, v in per.items() if v[0] < v[1])
    if bad:
        print("worst problems:", ", ".join("%s(%d/%d)" % (k, per[k][0], per[k][1]) for _, k in bad[:12]))
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
