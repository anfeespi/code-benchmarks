"""v4-strict test authoring kit.

One module per category (codebench/strict/<category>.py) registers a Spec per problem:

    @register("peak-concurrency-and-its-first-instant")
    class _:
        def brute(intervals): ...                 # independent reference, written from the prompt
        def gen(rng): return (intervals,)         # random args for the cross-check (seeded rng)
        def cases(rng): return [case(...), ...]   # new strict cases (code snippets, no expected)
        # optional:
        # call(fn, args) -> value                 # how to invoke an implementation (default fn(*args))
        # n_cross = 500                           # cross-check iterations (>= 500)
        # note = "..."                            # one line: what the reference is

`build_strict` cross-checks brute vs canonical on n_cross seeded inputs, prepends the v4 cases
(names prefixed "v4:"), fills `expected` from the canonical solution and checks that the canonical
passes 100%. Expected values are never hand-written.

Every case must be justified by the prompt text: unspecified behavior is not tested.
"""
import random

REGISTRY = {}


class Raised:
    """Outcome of a call that raised: compared by type name (and message when with_msg)."""

    def __init__(self, exc, with_msg=False):
        self.type = type(exc).__name__
        self.msg = str(exc) if with_msg else None

    def __eq__(self, other):
        return isinstance(other, Raised) and self.type == other.type and self.msg == other.msg

    def __repr__(self):
        return "Raised(%s%s)" % (self.type, ", %r" % self.msg if self.msg is not None else "")


def outcome(fn, args, call=None, with_msg=False):
    try:
        return call(fn, args) if call else fn(*args)
    except Exception as e:  # noqa: BLE001
        return Raised(e, with_msg)


def register(slug):
    def deco(cls):
        REGISTRY[slug] = cls
        return cls
    return deco


def case(name, code, timeout_s=5):
    return {"name": name, "code": code, "timeout_s": timeout_s}


def lit(x):
    """Python literal for a value (repr); floats such as nan/inf must be built in code instead.
    Sets/frozensets are rendered with sorted elements so the generated JSON does not depend on
    PYTHONHASHSEED."""
    if isinstance(x, (set, frozenset)):
        body = ", ".join(sorted((lit(v) for v in x)))
        if isinstance(x, frozenset):
            return "frozenset({%s})" % body if x else "frozenset()"
        return "{%s}" % body if x else "set()"
    if isinstance(x, tuple):
        return "(%s)" % (", ".join(lit(v) for v in x) + ("," if len(x) == 1 else ""))
    if isinstance(x, list):
        return "[%s]" % ", ".join(lit(v) for v in x)
    if isinstance(x, dict):
        return "{%s}" % ", ".join("%s: %s" % (lit(k), lit(v)) for k, v in x.items())
    return repr(x)


def call_case(name, entry, *args, timeout_s=5, **kwargs):
    """case calling sol.<entry>(*args, **kwargs) with literal arguments."""
    parts = [lit(a) for a in args] + ["%s=%s" % (k, lit(v)) for k, v in kwargs.items()]
    return case(name, "result = sol.%s(%s)" % (entry, ", ".join(parts)), timeout_s)


def batch_case(name, entry, arg_tuples, timeout_s=5):
    """One case evaluating several literal inputs; result is the list of outputs."""
    code = "result = [sol.%s(*a) for a in %s]" % (entry, lit([tuple(a) for a in arg_tuples]))
    return case(name, code, timeout_s)


def msg_case(name, call_expr, exc="ValueError", timeout_s=5):
    """case capturing (exception type, message) when the prompt specifies the exact message.
    If no exception is raised the result is ('no exception', <value>)."""
    code = ("try:\n    _v = %s\n    result = ('no exception', _v)\nexcept %s as _e:\n"
            "    result = (type(_e).__name__, str(_e))" % (call_expr, exc))
    return case(name, code, timeout_s)


def rng_for(slug, salt=0):
    return random.Random("%s:%d" % (slug, salt))
