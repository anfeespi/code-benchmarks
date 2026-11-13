"""Publish the benchmark to Braintrust, project `code-benchmarks`.

Two things go up:

- the suites as datasets, one row per problem with everything needed to grade an
  answer again: the prompt, the reference solution and the tests (v4 also carries
  the strict tests). Row ids are the problem slugs, so a re-upload updates rows in
  place instead of duplicating them.
- a scored outputs file as an experiment linked to its suite's dataset: the code the
  model returned, its scores (v4 also the strict ones) and the run metadata.

Usage:
  python -m codebench.publish dataset --suite v4          # dataset code-bench-v4
  python -m codebench.publish dataset --suite hard-v1     # dataset code-bench-hard-v1
  python -m codebench.publish run data/outputs/code-bench-hard-v1__gpt-6.1-sol.json [--name ...] [--note ...]
Key: BRAINTRUST_API_KEY in the environment.

The agentic suite is a Go service with patches, not rows: it stays in the repository.
"""
import argparse
import json
import os
import urllib.request
from pathlib import Path

from . import harness

API = "https://api.braintrust.dev/v1/"
PROJECT = "code-benchmarks"
# Rows carry whole test files (up to ~0.3 MB each for strict): small batches keep
# every request well under the API's body limit.
BATCH = 4


def _req(method, path, key, body=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def _insert(kind, obj_id, events, key):
    for i in range(0, len(events), BATCH):
        _req("POST", "%s/%s/insert" % (kind, obj_id), key, {"events": events[i:i + BATCH]})


def _project(key, name):
    found = [p for p in _req("GET", "project?limit=200", key)["objects"] if p["name"] == name]
    if not found:
        raise SystemExit("no Braintrust project %r" % name)
    return found[0]


def _dataset(key, project_id, suite):
    """The suite's dataset, created on first use (POST returns the existing one by name)."""
    return _req("POST", "dataset", key, {"project_id": project_id, "name": harness.SUITES[suite]["prefix"],
                                          "description": "Problems, reference solutions and tests of the %s suite." % suite})


def publish_dataset(key, suite, project):
    harness.use_suite(suite)
    proj = _project(key, project)
    ds = _dataset(key, proj["id"], suite)
    events = []
    for p in harness.load_problems():
        tests = harness.load_tests(p["slug"])
        if tests is None:
            raise SystemExit("no tests for %s" % p["slug"])
        expected = {"canonical_solution": p["canonical_solution"], "tests": tests["cases"]}
        if suite == harness.DEFAULT_SUITE:
            strict = harness.load_tests(p["slug"], "strict")
            if strict is not None:
                expected["strict_tests"] = strict["cases"]
        events.append({"id": p["slug"],
                       "input": {"entry_point": p["entry_point"], "prompt": p["prompt"]},
                       "expected": expected,
                       "metadata": {"suite": suite, "slug": p["slug"], "title": p["title"], "category": p.get("category"),
                                    "n_tests": len(tests["cases"]), "n_strict_tests": len(expected.get("strict_tests", []))}})
    _insert("dataset", ds["id"], events, key)
    print("dataset", ds["name"], ds["id"], len(events), "rows")


def publish_run(key, path, name, note, project):
    suite = harness.suite_for_output(path)
    harness.use_suite(suite)
    proj = _project(key, project)
    ds = _dataset(key, proj["id"], suite)
    name = name or Path(path).stem
    # POST experiment with a name already taken returns that experiment, and the
    # rows would be added to an old run: refuse and ask for another name.
    taken = {e["name"] for e in _req("GET", "experiment?project_id=%s&limit=1000" % proj["id"], key)["objects"]}
    if name in taken:
        raise SystemExit("experiment %r already exists in %s; pass --name" % (name, project))
    exp = _req("POST", "experiment", key, {"project_id": proj["id"], "name": name, "dataset_id": ds["id"],
                                             "metadata": {"note": note, "suite": suite, "source": str(path)}})
    probs = {p["title"]: p for p in harness.load_problems()}
    events = []
    for r in json.load(open(path)):
        if not r.get("scores"):
            raise SystemExit("file is not scored; run codebench.score --write first")
        p = probs[r["title"]]
        scores = dict(r["scores"])
        strict = (r.get("scores_by_suite") or {}).get("strict")
        if strict:
            scores.update({"strict_" + k: v for k, v in strict.items()})
        events.append({"input": {"entry_point": p["entry_point"], "prompt": p["prompt"]},
                       "output": {"code": r["code"]},
                       "expected": {"canonical_solution": p["canonical_solution"]},
                       "scores": scores,
                       "metadata": dict(r.get("metadata") or {}, slug=p["slug"], detail=r.get("detail")),
                       "origin": {"object_type": "dataset", "object_id": ds["id"], "id": p["slug"]}})
    _insert("experiment", exp["id"], events, key)
    print("experiment", exp["name"], exp["id"], len(events), "rows")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dataset", help="upload a suite as a dataset")
    d.add_argument("--suite", default=harness.DEFAULT_SUITE, choices=sorted(harness.SUITES))
    r = sub.add_parser("run", help="publish a scored outputs file as an experiment")
    r.add_argument("file")
    r.add_argument("--name", help="experiment name (default: the file name)")
    r.add_argument("--note", default="")
    for s in (d, r):
        s.add_argument("--project", default=PROJECT)
    a = ap.parse_args()
    key = os.environ["BRAINTRUST_API_KEY"]
    if a.cmd == "dataset":
        publish_dataset(key, a.suite, a.project)
    else:
        publish_run(key, a.file, a.name, a.note, a.project)


if __name__ == "__main__":
    main()
