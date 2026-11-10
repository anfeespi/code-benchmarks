"""Small type algebra used to give every problem one signature for all languages.

Types are plain JSON-able values:
  "int" | "float" | "bool" | "str" | "null" | "unknown" | "dynamic"
  ["list", T] | ["tuple", T1, ..., Tn] | ["map", K, V] | ["optional", T]

"dynamic" is where the Python values do not fit one static type (an op log mixing
ints, strings and None). Those positions travel as a tagged JSON value.
"""
import math

UNKNOWN = "unknown"
DYNAMIC = "dynamic"


def infer(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    if isinstance(v, tuple):
        return ["tuple"] + [infer(x) for x in v]
    if isinstance(v, list):
        t = UNKNOWN
        for x in v:
            t = unify(t, infer(x))
        return ["list", t]
    if isinstance(v, dict):
        k = t = UNKNOWN
        for a, b in v.items():
            k, t = unify(k, infer(a)), unify(t, infer(b))
        return ["map", k, t]
    return DYNAMIC


def _kind(t):
    return t if isinstance(t, str) else t[0]


def unify(a, b):
    if a == b:
        return a
    if a == UNKNOWN:
        return b
    if b == UNKNOWN:
        return a
    if DYNAMIC in (a, b):
        return DYNAMIC
    ka, kb = _kind(a), _kind(b)
    if isinstance(a, str) and isinstance(b, str) and {a, b} == {"int", "float"}:
        return "float"
    if ka == "null" or kb == "null":
        other = b if ka == "null" else a
        return other if _kind(other) == "optional" else ["optional", other]
    if ka == "optional" or kb == "optional":
        ia = a[1] if ka == "optional" else a
        ib = b[1] if kb == "optional" else b
        inner = unify(ia, ib)
        return inner if inner == DYNAMIC else ["optional", inner]
    if ka == kb == "list":
        return ["list", unify(a[1], b[1])]
    if ka == kb == "tuple":
        if len(a) == len(b):
            return ["tuple"] + [unify(x, y) for x, y in zip(a[1:], b[1:])]
        return DYNAMIC
    if ka == kb == "map":
        return ["map", unify(a[1], b[1]), unify(a[2], b[2])]
    return DYNAMIC


def fits(value_type, declared):
    """True when a value of value_type can be passed where declared is expected."""
    return unify(value_type, declared) == declared


def has_dynamic(sig):
    def walk(t):
        if t == DYNAMIC:
            return True
        return not isinstance(t, str) and any(walk(x) for x in t[1:])
    return any(walk(t) for t in sig["args"]) or walk(sig["returns"])


def show(t):
    if isinstance(t, str):
        return t
    if t[0] == "list":
        return "list<%s>" % show(t[1])
    if t[0] == "optional":
        return "%s?" % show(t[1])
    if t[0] == "map":
        return "map<%s,%s>" % (show(t[1]), show(t[2]))
    return "(%s)" % ", ".join(show(x) for x in t[1:])


def encode(v):
    """JSON wire form. Tuples become arrays, non-string-keyed maps become pair lists,
    and non-finite floats are tagged; the signature tells the reader which is which."""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return {"__float__": repr(v)}
    if isinstance(v, (list, tuple)):
        return [encode(x) for x in v]
    if isinstance(v, dict):
        if all(isinstance(k, str) for k in v):
            return {k: encode(x) for k, x in v.items()}
        return {"__pairs__": [[encode(k), encode(x)] for k, x in v.items()]}
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    return {"__repr__": repr(v)}


def encode_call(call):
    out = {"args": [encode(a) for a in call["args"]]}
    if "error" in call:
        out["error"] = call["error"]
    else:
        out["value"] = encode(call["value"])
    return out
