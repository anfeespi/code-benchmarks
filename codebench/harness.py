"""code-bench harness: execution-graded pass@1 for the 48 in-house problems.

Layout
  data/problems/code-bench-v2.json   48 problems (prompt, entry_point, canonical_solution)
  tests/<slug>.json                  test cases per problem (see TEST FORMAT)
  data/outputs/<experiment>.json     stored model outputs (from Braintrust)

TEST FORMAT (tests/<slug>.json)
  {"title": ..., "entry_point": ..., "cases": [
     {"name": "basic", "code": "result = sol.f(1, 2)", "timeout_s": 5},
     {"name": "raises", "code": "result = sol.f(None)", "raises": "TypeError"}
  ]}
Each case is a Python snippet executed in a child process with the candidate module
imported as `sol`; it must assign `result`. The expected value is NOT hand-written:
`build_expected` runs the same snippet against the canonical solution and stores it
under "expected" (JSON, tuples become lists) or {"raises": "<ExceptionName>"}.

Scores per candidate (same semantics as the July runs):
  checker      1 if the module imports and defines the entry point, else 0
  tests_ratio  passed / total
  pass         1 if every case passed
"""
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROBLEMS = ROOT / "data" / "problems" / "code-bench-v2.json"
TESTS_DIR = ROOT / "tests"
DEFAULT_TIMEOUT = 5.0
MEM_LIMIT_MB = 1024


def _pick_python():
    """Interpreter for the sandboxed child. The prompts never pin a Python version, so
    candidates are run on a modern interpreter (3.10+ syntax such as `int | None` and
    `bisect(key=)` must not count as failures). Override with CODEBENCH_PYTHON."""
    if os.environ.get("CODEBENCH_PYTHON"):
        return os.environ["CODEBENCH_PYTHON"]
    for cand in ("python3.13", "python3.12", "python3.11", "python3.10"):
        for d in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"):
            p = Path(d) / cand
            if p.exists():
                return str(p)
    return sys.executable


PYTHON = _pick_python()

CHILD = r'''
import json, sys, resource, importlib.util, traceback, math
spec = json.loads(sys.stdin.read())
try:
    resource.setrlimit(resource.RLIMIT_AS, (spec["mem"] * 1024 * 1024, spec["mem"] * 1024 * 1024))
except Exception:
    pass
def norm(v):
    if isinstance(v, (bool, int, str)) or v is None:
        return v
    if isinstance(v, float):
        return {"__float__": repr(v)} if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(v, (list, tuple)):
        return [norm(x) for x in v]
    if isinstance(v, (set, frozenset)):
        return {"__set__": sorted((norm(x) for x in v), key=repr)}
    if isinstance(v, dict):
        return {"__dict__": [[norm(k), norm(x)] for k, x in v.items()]}
    if isinstance(v, (bytes, bytearray)):
        return {"__bytes__": list(v)}
    return {"__repr__": repr(v)}
out = {"ok": False}
try:
    s = importlib.util.spec_from_file_location("sol", spec["sol_path"])
    sol = importlib.util.module_from_spec(s)
    s.loader.exec_module(sol)
    if not hasattr(sol, spec["entry_point"]):
        out["import_error"] = "entry point %s not defined" % spec["entry_point"]
    else:
        out["loaded"] = True
        if spec.get("code") is not None:
            ns = {"sol": sol, "math": math}
            try:
                exec(spec["code"], ns)
                out["ok"] = True
                out["value"] = norm(ns.get("result"))
            except Exception as e:
                out["exc"] = type(e).__name__
                out["exc_msg"] = str(e)[:300]
except SystemExit:
    out["import_error"] = "SystemExit during import"
except BaseException as e:
    out["import_error"] = "%s: %s" % (type(e).__name__, str(e)[:300])
sys.stdout.write(json.dumps(out))
'''


def slugify(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]


def load_problems():
    probs = json.load(open(PROBLEMS))
    for p in probs:
        p["slug"] = slugify(p["title"])
    return probs


def load_tests(slug):
    path = TESTS_DIR / (slug + ".json")
    return json.load(open(path)) if path.exists() else None


def run_case(sol_path, entry_point, code, timeout, mem=MEM_LIMIT_MB):
    spec = {"sol_path": str(sol_path), "entry_point": entry_point, "code": code, "mem": mem}
    try:
        proc = subprocess.run([PYTHON, "-I", "-c", CHILD], input=json.dumps(spec), capture_output=True,
                              text=True, timeout=timeout, cwd=os.path.dirname(sol_path))
    except subprocess.TimeoutExpired:
        return {"ok": False, "timeout": True}
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {"ok": False, "crash": (proc.stderr or proc.stdout)[-400:]}


def _write_sol(code):
    d = tempfile.mkdtemp(prefix="cb_")
    p = Path(d) / "sol.py"
    p.write_text(code or "")
    return p


def loads_ok(code, entry_point):
    p = _write_sol(code)
    r = run_case(p, entry_point, None, DEFAULT_TIMEOUT)
    return bool(r.get("loaded")), r.get("import_error") or r.get("crash") or ("timeout" if r.get("timeout") else None)


def outcome_matches(expected, got):
    """expected/got are child results; compare value or exception type."""
    if "raises" in expected:
        return got.get("exc") == expected["raises"]
    if not got.get("ok"):
        return False
    return _eq(expected.get("value"), got.get("value"))


def _eq(a, b):
    if isinstance(a, float) or isinstance(b, float):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
            return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
        return False
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_eq(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        if "__dict__" in a and "__dict__" in b:
            da = {json.dumps(k, sort_keys=True): v for k, v in a["__dict__"]}
            db = {json.dumps(k, sort_keys=True): v for k, v in b["__dict__"]}
            return da.keys() == db.keys() and all(_eq(da[k], db[k]) for k in da)
        return a == b
    return a == b


def score_candidate(problem, code, tests=None, verbose=False):
    """Return dict(checker, tests_ratio, pass, detail)."""
    tests = tests or load_tests(problem["slug"])
    if tests is None:
        raise RuntimeError("no tests for " + problem["slug"])
    if not (code or "").strip():
        return {"checker": 0, "tests_ratio": 0.0, "pass": 0, "detail": ["empty output"]}
    ok, err = loads_ok(code, problem["entry_point"])
    if not ok:
        return {"checker": 0, "tests_ratio": 0.0, "pass": 0, "detail": ["import: %s" % err]}
    sol_path = _write_sol(code)
    passed, detail = 0, []
    for c in tests["cases"]:
        got = run_case(sol_path, problem["entry_point"], c["code"], c.get("timeout_s", DEFAULT_TIMEOUT))
        exp = c["expected"] if "expected" in c else {"raises": c["raises"]}
        hit = outcome_matches(exp, got)
        passed += hit
        if not hit:
            detail.append("%s: expected %s got %s" % (c["name"], json.dumps(exp)[:120], json.dumps(got)[:160]))
    n = len(tests["cases"])
    ratio = passed / n if n else 0.0
    return {"checker": 1, "tests_ratio": round(ratio, 4), "pass": int(passed == n), "detail": detail}


def build_expected(problem, tests):
    """Fill/overwrite `expected` in each case by running the canonical solution."""
    sol_path = _write_sol(problem["canonical_solution"])
    ok, err = loads_ok(problem["canonical_solution"], problem["entry_point"])
    if not ok:
        raise RuntimeError("canonical does not load for %s: %s" % (problem["slug"], err))
    for c in tests["cases"]:
        got = run_case(sol_path, problem["entry_point"], c["code"], c.get("timeout_s", DEFAULT_TIMEOUT))
        if got.get("timeout"):
            raise RuntimeError("canonical timed out on case %s of %s" % (c["name"], problem["slug"]))
        if got.get("ok"):
            c.pop("raises", None)
            c["expected"] = {"value": got["value"]}
        elif got.get("exc"):
            c.pop("expected", None)
            c["raises"] = got["exc"]
        else:
            raise RuntimeError("canonical crashed on %s/%s: %s" % (problem["slug"], c["name"], got))
    return tests


def extract_code(text):
    """Pull the Python code out of a model answer (fenced block preferred)."""
    if not text:
        return ""
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, flags=re.S)
    if blocks:
        return max(blocks, key=len).strip("\n")
    return text.strip()
