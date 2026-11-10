"""Turn the Python test snippets of a suite into language-neutral call records.

A hard-suite case is a Python snippet that calls the solution one or more times and
often digests the result. Other languages cannot run that snippet, so each case is
executed once against the canonical solution with a recording proxy: every call to
the entry point is captured as (arguments, returned value or raised error). A
candidate in any language then passes the case when every recorded call returns the
recorded value. That is at least as strict as the original digest.

Usage:
  python -m codebench.multilang.materialize types            # inferred signature per problem
  python -m codebench.multilang.materialize build [slug...]  # write data/cache/neutral/<slug>.json
"""
import copy
import json
import sys
import types as pytypes

from .. import harness
from . import typesys

CACHE = harness.ROOT / "data" / "cache" / "neutral"


def record_cases(problem, tests):
    """Run every case against the canonical solution and return the recorded calls."""
    ep = problem["entry_point"]
    mod = pytypes.ModuleType("sol")
    exec(problem["canonical_solution"], mod.__dict__)
    real = getattr(mod, ep)
    out = []
    for case in tests["cases"]:
        calls = []

        def proxy(*args, **kwargs):
            if kwargs:
                raise TypeError("keyword arguments are not portable")
            frozen = copy.deepcopy(args)
            try:
                value = real(*args)
            except Exception as exc:  # the canonical raising is the expected outcome
                calls.append({"args": frozen, "error": type(exc).__name__})
                raise
            calls.append({"args": frozen, "value": copy.deepcopy(value)})
            return value

        setattr(mod, ep, proxy)
        try:
            exec(case["code"], {"sol": mod})
        except Exception:
            pass  # a raising case is recorded through the proxy
        out.append({"name": case["name"], "timeout_s": case.get("timeout_s"), "calls": calls})
    setattr(mod, ep, real)
    return out


def load_suite():
    harness.use_suite("hard-v1")
    for p in harness.load_problems():
        yield p, harness.load_tests(p["slug"])


def signature(recorded):
    """Unified type of every argument position and of the return value.

    Only calls that returned a value shape the signature. Many error cases pass a
    wrong type on purpose (None where a list is expected); a statically typed
    language cannot even express that call, so it must not widen the signature.
    """
    args, ret, raises = None, typesys.UNKNOWN, False
    for case in recorded:
        for call in case["calls"]:
            if "error" in call:
                continue
            ts = [typesys.infer(a) for a in call["args"]]
            args = ts if args is None else [typesys.unify(a, b) for a, b in zip(args, ts)]
            ret = typesys.unify(ret, typesys.infer(call["value"]))
    args = args or []
    dropped = 0
    for case in recorded:
        for call in case["calls"]:
            if "error" not in call:
                continue
            fits = len(call["args"]) == len(args) and all(
                typesys.fits(typesys.infer(a), t) for a, t in zip(call["args"], args))
            call["typed"] = fits
            raises = raises or fits
            dropped += not fits
    return {"args": args, "returns": ret, "raises": raises, "untyped_error_calls": dropped}


def main(argv=None):
    argv = argv or sys.argv[1:]
    cmd, only = (argv[0] if argv else "types"), set(argv[1:])
    for p, tests in load_suite():
        if only and p["slug"] not in only:
            continue
        rec = record_cases(p, tests)
        sig = signature(rec)
        if cmd == "types":
            flag = "DYNAMIC " if typesys.has_dynamic(sig) else "        "
            print("%s%-36s %s(%s) -> %s%s" % (flag, p["slug"], p["entry_point"],
                  ", ".join(typesys.show(t) for t in sig["args"]), typesys.show(sig["returns"]),
                  ("  [raises]" if sig["raises"] else "") + ("  [-%d untyped]" % sig["untyped_error_calls"] if sig["untyped_error_calls"] else "")))
        else:
            CACHE.mkdir(parents=True, exist_ok=True)
            doc = {"slug": p["slug"], "entry_point": p["entry_point"], "signature": sig,
                   "cases": [{"name": c["name"], "timeout_s": c["timeout_s"],
                              "calls": [dict(typesys.encode_call(k), **({"typed": k["typed"]} if "typed" in k else {}))
                                        for k in c["calls"]]} for c in rec]}
            (CACHE / (p["slug"] + ".json")).write_text(json.dumps(doc))


if __name__ == "__main__":
    main()
