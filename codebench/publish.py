"""Publish a scored outputs file as a Braintrust experiment in project `code-benchmarks`.

Usage:
  python -m codebench.publish data/outputs/code-bench-v4__fable-5.1.json --name code-bench-v4__fable-5.1 \
      --note "v4 suite (rebuilt 2026-09), fresh generation"
Key: BRAINTRUST_API_KEY in the environment.
"""
import argparse
import json
import os
import urllib.request

from .harness import load_problems

API = "https://api.braintrust.dev/v1/"


def _req(method, path, key, body=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--name", required=True)
    ap.add_argument("--note", default="")
    ap.add_argument("--project", default="code-benchmarks")
    a = ap.parse_args()
    key = os.environ["BRAINTRUST_API_KEY"]
    proj = [p for p in _req("GET", "project?limit=200", key)["objects"] if p["name"] == a.project][0]
    exp = _req("POST", "experiment", key, {"project_id": proj["id"], "name": a.name,
                                             "metadata": {"note": a.note, "suite": "code-bench-v4", "source": a.file}})
    probs = {p["title"]: p for p in load_problems()}
    rows = json.load(open(a.file))
    events = []
    for r in rows:
        p = probs[r["title"]]
        if not r.get("scores"):
            raise SystemExit("file is not scored; run codebench.score --write first")
        events.append({"input": {"entry_point": p["entry_point"], "prompt": p["prompt"]},
                       "output": {"code": r["code"]},
                       "expected": {"canonical_solution": p["canonical_solution"]},
                       "scores": r["scores"],
                       "metadata": dict(r.get("metadata") or {}, detail=r.get("detail"))})
    for i in range(0, len(events), 20):
        _req("POST", "experiment/%s/insert" % exp["id"], key, {"events": events[i:i + 20]})
    print("published", a.name, exp["id"], len(events), "rows")


if __name__ == "__main__":
    main()
