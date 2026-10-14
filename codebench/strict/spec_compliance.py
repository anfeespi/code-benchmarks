"""v4-strict specs: spec_compliance.

Every prompt in this category states its error messages as "message contains <substring>", so
error cases record (exception type, [substring in str(e) for each required substring]) and never
the full message text. The required substrings come from the reference (written from the prompt);
`_mixed_batch` also asserts that the canonical agrees with the reference on every literal input.
Success values are recorded with type names wherever the prompt pins a type (int result, float
fields, tuples, same objects) because the harness compares 14 == 14.0 and [1, 2] == (1, 2).
"""
import string

from . import register, case, lit

_CANON = {}


def _canon(slug, entry):
    if slug not in _CANON:
        from ..harness import load_problems
        p = [q for q in load_problems() if q["slug"] == slug][0]
        ns = {}
        exec(compile(p["canonical_solution"], "<canonical>", "exec"), ns)
        _CANON[slug] = ns[entry]
    return _CANON[slug]


class RefErr(Exception):
    """Reference error: `etype` is the required exception type, `subs` the required substrings."""

    def __init__(self, etype, *subs):
        super().__init__(" | ".join(subs))
        self.etype = etype
        self.subs = list(subs)


def _typed(v):
    if isinstance(v, (list, tuple)):
        return (type(v).__name__, [_typed(x) for x in v])
    return (type(v).__name__, v)


def _run(ref, fn, args, norm):
    """Outcome of fn(*args) judged against the reference's error contract."""
    try:
        ref(*args)
        rexc = None
    except RefErr as e:
        rexc = e
    try:
        v = fn(*args)
    except RefErr as e:
        return ("raised", e.etype, True)
    except Exception as e:  # noqa: BLE001
        if rexc is None:
            return ("raised", type(e).__name__, None)
        return ("raised", type(e).__name__, all(s in str(e) for s in rexc.subs))
    return ("ok", norm(v))


def _make_call(ref, norm=_typed):
    def call(fn, args):
        return _run(ref, fn, args, norm)
    return call


T_SNIP = ("def _t(v):\n"
          "    if isinstance(v, (list, tuple)):\n"
          "        return [type(v).__name__, [_t(x) for x in v]]\n"
          "    return [type(v).__name__, v]\n")


def _mixed_batch(name, slug, entry, ref, arg_tuples, norm_code="_t(_v)", check_unchanged=False,
                 norm=_typed, timeout_s=5):
    """One case over several literal inputs: ('ok', normalized value [, input unchanged]) or
    (exception type, [required substring present ...]). Asserts canonical == reference first."""
    canon = _canon(slug, entry)
    rows = []
    for a in arg_tuples:
        a = tuple(a)
        got = _run(ref, canon, a, norm)
        want = _run(ref, ref, a, norm)
        assert got == want, (slug, name, a, got, want)
        try:
            ref(*a)
            subs = []
        except RefErr as e:
            subs = e.subs
        rows.append((a, subs))
    code = T_SNIP + "out = []\nfor _a, _subs in %s:\n" % lit(rows)
    if check_unchanged:
        code += "    _snap = repr(_a)\n"
    code += ("    try:\n        _v = sol.%s(*_a)\n        _r = ['ok', %s]\n"
             "    except Exception as _e:\n        _r = [type(_e).__name__, [_s in str(_e) for _s in _subs]]\n"
             % (entry, norm_code))
    if check_unchanged:
        code += "    _r.append(repr(_a) == _snap)\n"
    code += "    out.append(_r)\nresult = out"
    return case(name, code, timeout_s)


def _err_case(name, entry, exprs_subs):
    """Errors on hand-written calls (exprs may build values in code). exprs_subs: [(expr, [subs])]."""
    code = "out = []\n"
    for expr, subs in exprs_subs:
        code += ("try:\n    _v = sol.%s(%s)\n    out.append(('no error', repr(_v)))\nexcept Exception as _e:\n"
                 "    out.append((type(_e).__name__, [_s in str(_e) for _s in %s]))\n" % (entry, expr, lit(subs)))
    return case(name, code + "result = out")


# ---------------------------------------------------------------------------------------------
SUM = "category-summarizer-with-indexed-validation-errors"


def _sum_ref(rows):
    if not isinstance(rows, list):
        raise RefErr("TypeError", "rows must be a list")
    out = {}
    for i, row in enumerate(rows):
        tag = "row %d" % i
        if not isinstance(row, tuple) or len(row) != 3:
            raise RefErr("TypeError", tag)
        c, a, r = row
        if not isinstance(c, str) or c == "":
            raise RefErr("ValueError", tag)
        if isinstance(a, bool) or not isinstance(a, (int, float)):
            raise RefErr("TypeError", tag)
        if a < 0:
            raise RefErr("ValueError", tag)
        if not isinstance(r, bool):
            raise RefErr("TypeError", tag)
    for c, a, r in rows:
        out.setdefault(c, []).append((a, r))
    res = {}
    for c, lst in out.items():
        gross = 0.0
        net = 0.0
        for a, r in lst:
            gross += float(a)
            if not r:
                net += float(a)
        res[c] = {"count": len(lst), "gross": gross, "net": net,
                  "largest": float(sorted(a for a, _ in lst)[-1])}
    return res


def _sum_norm(r):
    return [(k, sorted((kk, type(vv).__name__, vv) for kk, vv in v.items())) for k, v in r.items()]


SUM_NORM_CODE = "[[k, sorted((kk, type(vv).__name__, vv) for kk, vv in v.items())] for k, v in _v.items()]"
_CATS = ["food", "tech", "a", "B", "zz", "café", "日本", " ", "x y", "0"]


def _sum_valid_row(rng):
    c = rng.choice(_CATS)
    k = rng.random()
    if k < 0.45:
        a = rng.randint(0, 1000)
    elif k < 0.9:
        a = round(rng.uniform(0, 1000), rng.choice([0, 1, 2, 3]))
    else:
        a = rng.choice([0, 0.0, 10 ** 15, 1e-9, 2 ** 53])
    return (c, a, rng.random() < 0.4)


def _sum_bad_row(rng):
    kind = rng.choice("aabcdee")
    c, a, r = _sum_valid_row(rng)
    if kind == "a":
        return rng.choice([[c, a, r], (c, a), (c, a, r, r), (), "abc", None, {c: a}, (c,), 5])
    if kind == "b":
        return (rng.choice(["", 5, None, b"x", ("a",), 1.5, True]), a, r)
    if kind == "c":
        return (c, rng.choice([True, False, "1", None, [1], b"1", 1j]), r)
    if kind == "d":
        return (c, rng.choice([-1, -0.5, -1e-9, -10 ** 12]), r)
    return (c, a, rng.choice([0, 1, None, "False", "", 1.0]))


def _sum_multi_bad_row(rng):
    """Rows breaking several checks at once: the earliest check in a..e must win."""
    return rng.choice([
        ("", True, None), (5, "x", 0), ("", -1, 0), ("ok", True, 0), ("ok", "1", "x"),
        ("ok", -3, None), (None, -1, None), ("", None, None), (b"", -2.5, 1), ("q", -0.1, "no"),
    ])


def _sum_rows(rng, err_rate=0.35):
    n = rng.choice([0, 1, 2, 3, 5, 8, 15, 30])
    rows = [_sum_valid_row(rng) for _ in range(n)]
    if rows and rng.random() < err_rate:
        for _ in range(rng.choice([1, 1, 2, 3])):
            pos = rng.randrange(len(rows) + 1)
            rows.insert(pos, _sum_multi_bad_row(rng) if rng.random() < 0.3 else _sum_bad_row(rng))
    return rows


@register(SUM)
class Summarize:
    note = "reference from the prompt: validate rows a..e then aggregate per category (sorted for largest)"
    n_cross = 600

    def brute(rows):
        return _sum_ref(rows)

    def gen(rng):
        r = rng.random()
        if r < 0.03:
            return (rng.choice([("a", 1, False), None, "rows", {"a": 1}, (("a", 1, False),)]),)
        return (_sum_rows(rng),)

    call = staticmethod(_make_call(_sum_ref, _sum_norm))

    def cases(rng):
        mb = lambda name, args: _mixed_batch(name, SUM, "summarize_by_category", _sum_ref, args,  # noqa: E731
                                             norm_code=SUM_NORM_CODE, check_unchanged=True, norm=_sum_norm)
        out = [
            mb("single_row_types", [([("solo", 7, False)],), ([("solo", 7, True)],), ([("solo", 2.5, True)],)]),
            mb("all_refunded_net_zero_float", [([("a", 3, True), ("a", 4, True)],)]),
            mb("zero_amounts", [([("z", 0, False), ("z", 0.0, True)],), ([("z", 0, True)],)]),
            mb("largest_not_last", [([("a", 5, False), ("a", 9, True), ("a", 1, False)],),
                                    ([("a", 9.5, False), ("a", 9, False)],)]),
            mb("big_ints_become_float", [([("a", 10 ** 15, False), ("a", 2 ** 53, True)],)]),
            mb("unicode_and_space_categories", [([("café", 1, False), ("日本", 2, True), (" ", 3, False),
                                                  ("café", 4, True)],)]),
            mb("interleaved_category_order", [([("b", 1, False), ("a", 1, False), ("b", 1, False),
                                                ("c", 1, True), ("a", 2, False)],)]),
            mb("bad_row_shapes", [([("a", 1, False), [("a", 1, False)]],), ([("a", 1, False), ()],),
                                  ([("a", 1, False), ("a", 1, False), None],), ([5],), ([{"a": 1}],),
                                  ([("a", 1, False), ("a", 1, False, 1)],)]),
            mb("bad_category", [([("a", 1, False), ("", 1, False)],), ([(None, 1, False)],),
                                ([("a", 1, False), (b"a", 1, False)],), ([(("a",), 1, False)],)]),
            mb("bad_amount_type", [([("a", False, False)],), ([("a", 1, False), ("a", None, False)],),
                                   ([("a", [1], False)],), ([("a", 1j, False)],), ([("a", "0", True)],)]),
            mb("negative_amount", [([("a", -1e-9, False)],), ([("a", 1, False), ("b", 2, True), ("c", -10 ** 12, True)],)]),
            mb("bad_refunded", [([("a", 1, 1)],), ([("a", 1, False), ("a", 1, "True")],), ([("a", 1, None)],),
                                ([("a", 1, 0.0)],)]),
            mb("check_order_within_row", [([("", True, None)],), ([(5, -1, 0)],), ([("a", True, None)],),
                                          ([("a", "x", 0)],), ([("a", -1, None)],), ([("", -1, None)],)]),
            mb("first_invalid_row_wins", [([("a", 1, False), ("b", 2, False), ("c", 3, 1), ("", 1, False)],),
                                          ([("a", 1, False)] * 11 + [("a", -1, False), ("a", True, False)],),
                                          ([("a", 1, False)] * 12 + [None],)]),
            mb("rows_not_a_list", [((("a", 1, False),),), (None,), ("rows",), ({"a": (1, False)},)]),
            case("mutable_results_independent",
                 "rows = [('a', 1, False), ('b', 2.5, True)]\n"
                 "r1 = sol.summarize_by_category(rows)\n"
                 "r1['a']['count'] = 99\nr1['a']['gross'] = -1.0\nr1['zzz'] = {}\n"
                 "r2 = sol.summarize_by_category(rows)\n"
                 "result = (sorted(r2), r2['a']['count'], r2['a']['gross'], rows == [('a', 1, False), ('b', 2.5, True)])"),
            case("error_does_not_mutate_rows",
                 "rows = [('a', 1, False), ('a', 2, True), ('b', -1, False)]\nsnap = list(rows)\n"
                 "try:\n    sol.summarize_by_category(rows)\n    ok = 'no error'\nexcept ValueError as e:\n"
                 "    ok = 'row 2' in str(e)\nresult = (ok, rows == snap)"),
        ]
        for k in range(14):
            batch = [(_sum_rows(rng, err_rate=0.0 if k < 7 else 0.6),) for _ in range(8)]
            out.append(mb("random_batch_%02d" % k, batch))
        rows = []
        for _ in range(3000):
            rows.append(_sum_valid_row(rng))
        out.append(mb("larger_random_3000", [(rows,)]))
        return out


# ---------------------------------------------------------------------------------------------
CLAMP = "clamp-list-values-without-min-max"


def _num(x):
    return not isinstance(x, bool) and isinstance(x, (int, float))


def _clamp_ref(values, low, high):
    if not isinstance(values, list):
        raise RefErr("TypeError", "values must be a list")
    if not _num(low) or not _num(high):
        raise RefErr("TypeError", "bounds must be numbers")
    if low > high:
        raise RefErr("ValueError", "low must not exceed high")
    for i, v in enumerate(values):
        if not _num(v):
            raise RefErr("TypeError", "index %d" % i)
    return [low if v < low else high if v > high else v for v in values]


def _clamp_num(rng):
    return rng.choice([rng.randint(-50, 50), round(rng.uniform(-50, 50), 2), float(rng.randint(-50, 50)),
                       rng.choice([0, 0.0, -0.0, 10 ** 20, -10 ** 20, 1e300, -1e300])])


def _clamp_args(rng, err_rate=0.3):
    vals = [_clamp_num(rng) for _ in range(rng.choice([0, 1, 2, 4, 8, 15]))]
    lo, hi = _clamp_num(rng), _clamp_num(rng)
    if lo > hi:
        lo, hi = hi, lo
    if rng.random() < 0.15:
        hi = lo if rng.random() < 0.5 else float(lo)
    if rng.random() < err_rate:
        kind = rng.choice("vbblee")
        if kind == "v":
            vals = rng.choice([tuple(vals), None, "abc", {1: 2}])
        elif kind == "b":
            bad = rng.choice([True, False, None, "1", [1], 1j])
            lo, hi = (bad, hi) if rng.random() < 0.5 else (lo, bad)
        elif kind == "l":
            if lo != hi:
                lo, hi = hi, lo
        else:
            for _ in range(rng.choice([1, 2])):
                vals.insert(rng.randrange(len(vals) + 1), rng.choice([True, False, None, "x", [1], 1j, (1,)]))
    return (vals, lo, hi)


CLAMP_NORM = "[_t(_v), [_v[_i] is _a[0][_i] for _i in range(len(_v)) if _i < len(_a[0]) and _a[1] <= _a[0][_i] <= _a[2]]]"


def _clamp_norm(v):
    return _typed(v)


@register(CLAMP)
class Clamp:
    note = "reference from the prompt: checks 1-4 in order, then conditional expression per element"
    n_cross = 600

    def brute(values, low, high):
        return _clamp_ref(values, low, high)

    def gen(rng):
        return _clamp_args(rng)

    call = staticmethod(_make_call(_clamp_ref))

    def cases(rng):
        # each ok row: typed result + identity of every kept (in-range) element with the input element
        mb = lambda name, args: _mixed_batch(name, CLAMP, "clamp_values", _clamp_ref, args,  # noqa: E731
                                             norm_code=CLAMP_NORM, check_unchanged=True)
        out = [
            mb("boundary_values_kept_not_replaced", [([2.0, 6.0], 2, 6), ([2, 6], 2.0, 6.0), ([-0.0, 0], 0, 0)]),
            mb("clamped_takes_bound_type", [([1, 9], 2.5, 6.5), ([1.5, 9.5], 2, 6), ([-3, 3], -1.0, 1)]),
            mb("low_equals_high", [([1, 5, 9], 5, 5), ([5.0], 5, 5), ([], 3, 3)]),
            mb("empty_and_single", [([], 0, 1), ([7], 0, 1), ([0.5], 0, 1), ([-7], 0, 1)]),
            mb("huge_ints_exact", [([10 ** 30, -10 ** 30, 10 ** 30 + 1], -10 ** 30, 10 ** 30)]),
            mb("float_bounds_int_values", [([1, 2, 3, 4], 1.5, 3.5)]),
            mb("bad_bounds_variants", [([1], 0, True), ([1], False, 1), ([1], "0", 1), ([1], 0, None),
                                       ([1], 1j, 2), (["x"], True, 0)]),
            mb("low_gt_high_variants", [([1], 1, 0), ([], 0.5, 0.25), ([None], 2, 1), ([1], 10 ** 20, -10 ** 20)]),
            mb("values_not_list_first", [((1, 2), "a", 1), (None, 5, 1), ("abc", 0, 1), ({1, 2}, 0, 1)]),
            mb("bad_element_positions", [([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, "x"], 0, 5),
                                         ([True], 0, 1), ([1, False], 0, 1), ([1.5, 2, None, "y"], 0, 1),
                                         ([1, 2, (3,)], 0, 1), ([1j], 0, 1)]),
            case("infinite_bounds",
                 "inf = float('inf')\n"
                 "r = sol.clamp_values([1, -5.5, 10 ** 40, inf, -inf], -inf, inf)\n"
                 "r2 = sol.clamp_values([1, 2], 0, inf)\n"
                 "result = (r, [type(x).__name__ for x in r], r2)"),
            case("error_after_good_elements_no_side_effects",
                 "a = [5, -3, 99, 'bad', 2]\nsnap = list(a)\n"
                 "try:\n    sol.clamp_values(a, 0, 10)\n    r = 'no error'\nexcept TypeError as e:\n    r = 'index 3' in str(e)\n"
                 "result = (r, a == snap, all(x is y for x, y in zip(a, snap)))"),
        ]
        for k in range(12):
            out.append(mb("random_batch_%02d" % k, [_clamp_args(rng, 0.0 if k < 6 else 0.6) for _ in range(10)]))
        return out


# ---------------------------------------------------------------------------------------------
FLAT = "depth-limited-flatten-iteration-only"


def _flat_ref(nested, max_depth):
    if not isinstance(nested, list):
        raise RefErr("TypeError", "nested must be a list")
    if isinstance(max_depth, bool) or not isinstance(max_depth, int):
        raise RefErr("TypeError", "max_depth must be an int")
    if max_depth < 0:
        raise RefErr("ValueError", "max_depth must be >= 0")

    def go(lst, d):
        res = []
        for x in lst:
            if type(x) is list and d < max_depth:
                res.extend(go(x, d + 1))
            else:
                res.append(x)
        return res
    return go(nested, 0)


def _rand_nested(rng, depth=0):
    n = rng.choice([0, 1, 2, 3, 4])
    out = []
    for _ in range(n):
        r = rng.random()
        if r < 0.4 and depth < 6:
            out.append(_rand_nested(rng, depth + 1))
        elif r < 0.5:
            out.append((rng.randint(0, 9), [rng.randint(0, 9)]) if rng.random() < 0.5 else ())
        elif r < 0.6:
            out.append(rng.choice(["s", "", "ab", "日"]))
        elif r < 0.65:
            out.append({"k": [rng.randint(0, 9)]})
        elif r < 0.7:
            out.append(rng.choice([None, True, 1.5]))
        else:
            out.append(rng.randint(0, 99))
    return out


def _flat_args(rng, err_rate=0.15):
    nested = _rand_nested(rng)
    d = rng.choice([0, 0, 1, 1, 2, 3, 4, 10, 10 ** 20])
    if rng.random() < err_rate:
        kind = rng.choice("ntv")
        if kind == "n":
            nested = rng.choice([tuple(nested), "abc", None, {1: 2}])
            if rng.random() < 0.5:
                d = rng.choice([True, 2.0, -1])
        elif kind == "t":
            d = rng.choice([True, False, 2.0, "2", None, 1j])
        else:
            d = rng.choice([-1, -2, -10 ** 20])
    return (nested, d)


def _flat_norm(v):
    return _typed(v)


# typed result + every non-list element of the result is an object taken from the input
FLAT_NORM = ("[_t(_v), all(id(_x) in _ids(_a[0]) for _x in _v if type(_x) is not list)]")
FLAT_SNIP = ("def _ids(root):\n    seen = set()\n    st = [root]\n    while st:\n        c = st.pop()\n"
             "        seen.add(id(c))\n        if type(c) is list:\n            st.extend(c)\n    return seen\n")


@register(FLAT)
class Flatten:
    note = "reference from the prompt: recursive expansion of type-list elements while depth < max_depth"
    n_cross = 600

    def brute(nested, max_depth):
        return _flat_ref(nested, max_depth)

    def gen(rng):
        return _flat_args(rng)

    call = staticmethod(_make_call(_flat_ref))

    def cases(rng):
        def mb(name, args):
            c = _mixed_batch(name, FLAT, "flatten_depth", _flat_ref, args, norm_code=FLAT_NORM, check_unchanged=True)
            c["code"] = FLAT_SNIP + c["code"]
            return c
        out = [
            mb("empty_lists_vanish_when_expanded", [([[], [[]], [[], []]], 1), ([[], [[]], [[], []]], 2),
                                                     ([[[]]], 0), ([[[]]], 5)]),
            mb("depth_exactly_matches_nesting", [([[[[1]]]], 2), ([[[[1]]]], 3), ([[[[1]]]], 4)]),
            mb("tuples_strings_dicts_are_atoms", [([("a", [1]), "xy", {"k": [1]}, [("b",)]], 9),
                                                   ([[(1, [2, [3]])]], 3)]),
            mb("huge_max_depth", [([1, [2, [3]]], 10 ** 30)]),
            mb("validation_order", [((1, 2), True), ("x", -1), (None, 2.0), ([1], 2.0), ([1], True),
                                    ([1], -1), ([], -10 ** 20), ([], None), ([[1]], "1")]),
            case("depth_zero_same_element_objects",
                 "a = [[1], (2,), {'k': 3}, 'x']\nr = sol.flatten_depth(a, 0)\n"
                 "result = (r is not a, len(r), all(x is y for x, y in zip(r, a)))"),
            case("unexpanded_inner_list_is_original_object",
                 "inner = [3, [4]]\na = [1, [2, inner]]\nr = sol.flatten_depth(a, 1)\n"
                 "result = (r, r[2] is inner)"),
            case("deep_10000_full_flatten",
                 "node = ['leaf', 1]\nfor i in range(10000):\n    node = [i, node, (i,)] if i % 1000 == 0 else [node]\n"
                 "r = sol.flatten_depth(node, 10 ** 6)\nresult = (len(r), r[:6], r[-6:])", timeout_s=10),
            case("deep_6000_partial_depth",
                 "node = [0]\nfor _ in range(6000):\n    node = [node]\n"
                 "r = sol.flatten_depth(node, 2500)\n"
                 "d = 0\ncur = r\nwhile type(cur) is list and len(cur) == 1 and type(cur[0]) is list:\n"
                 "    cur = cur[0]\n    d += 1\n"
                 "result = (len(r), d, cur)", timeout_s=10),
            case("wide_and_deep_mix",
                 "a = []\nfor i in range(200):\n    x = [i]\n    for _ in range(i % 7):\n        x = [x, i]\n    a.append(x)\n"
                 "result = [sol.flatten_depth(a, d) for d in range(0, 8)]"),
        ]
        for k in range(12):
            out.append(mb("random_batch_%02d" % k, [_flat_args(rng, 0.0 if k < 8 else 0.5) for _ in range(10)]))
        return out


# ---------------------------------------------------------------------------------------------
DUR = "duration-string-parser-under-a-no-import-contract"


def _dur_ref(text):
    if not isinstance(text, str):
        raise RefErr("TypeError", "expected str")
    if text.strip() == "":
        raise RefErr("ValueError", "empty duration")
    i, n, total, nxt = 0, len(text), 0, 0
    if n == 0:
        raise RefErr("ValueError", "malformed duration")
    while i < n:
        j = i
        while j < n and text[j] in "0123456789":
            j += 1
        if j == i or j == n or text[j] not in "hms" or "hms".index(text[j]) < nxt:
            raise RefErr("ValueError", "malformed duration")
        nxt = "hms".index(text[j]) + 1
        total += int(text[i:j]) * {"h": 3600, "m": 60, "s": 1}[text[j]]
        i = j + 1
    return total


def _dur_valid(rng):
    while True:
        parts = []
        for u in "hms":
            if rng.random() < 0.55:
                parts.append("0" * rng.choice([0, 0, 0, 1, 3]) + str(rng.choice([rng.randint(0, 99), rng.randint(0, 10 ** 6),
                                                                                 rng.randint(0, 10 ** 25)])) + u)
        if parts:
            return "".join(parts)


def _dur_mutate(rng, s):
    k = rng.randrange(9)
    p = rng.randrange(len(s) + 1)
    if k == 0:
        return s[:p] + rng.choice([" ", "\t", "-", "+", ".", "x", "H", "M", "S", ",", "\n", "\u00a0", "١", "²"]) + s[p:]
    if k == 1:
        return s + s[-1]  # repeated unit or unit-unit
    if k == 2:
        return s + rng.choice(["1h", "2m", "3s", "5"])
    if k == 3:
        return s.upper()
    if k == 4:
        return rng.choice("hms") + s
    if k == 5:
        return s.rstrip("hms")
    if k == 6:
        return s.replace(rng.choice("hms"), "", 1)
    if k == 7:
        return s[::-1]
    return rng.choice(["1h2h", "1m1h", "1s1m", "m", "s", "h", "1", "1hm", "1h1m1s1s", "01.5m", "-0s", "+1h", "1 m"])


def _dur_args(rng):
    r = rng.random()
    s = _dur_valid(rng)
    if r < 0.45:
        return (s,)
    if r < 0.9:
        return (_dur_mutate(rng, s),)
    if r < 0.95:
        return (rng.choice(["", " ", "\t\n", "  \r\n "]),)
    return (rng.choice([s.encode(), 5, None, [s], 1.5, bytearray(b"1h")]),)


@register(DUR)
class Duration:
    note = "reference from the prompt: manual component scan with h<m<s order tracking"
    n_cross = 800

    def brute(text):
        return _dur_ref(text)

    def gen(rng):
        return _dur_args(rng)

    call = staticmethod(_make_call(_dur_ref))

    def cases(rng):
        mb = lambda name, args: _mixed_batch(name, DUR, "parse_duration", _dur_ref, args)  # noqa: E731
        out = [
            mb("each_single_component", [("0h",), ("1h",), ("1m",), ("1s",), ("59s",), ("3600s",), ("0000000s",)]),
            mb("all_pairs_in_order", [("1h2m",), ("1h2s",), ("1m2s",), ("01h02m03s",)]),
            mb("out_of_order_pairs", [("2m1h",), ("2s1h",), ("2s1m",), ("1s1m1h",), ("1h1s1m",)]),
            mb("repeated_components", [("1h1h",), ("1m1m",), ("1s1s",), ("1h2m1h",), ("1h2m3s4s",)]),
            mb("digits_without_unit", [("12",), ("1h30",), ("1h2m3",), ("0",)]),
            mb("unit_without_digits", [("h",), ("1hm",), ("ms",), ("1h2ms",), ("s1",)]),
            mb("uppercase_units", [("1H",), ("1h2M",), ("3S",)]),
            mb("signs_and_decimals", [("-1h",), ("+1h",), ("1.5h",), ("1h-2m",), (".5s",), ("1,5s",)]),
            mb("whitespace_inside_or_around", [("1h 2m",), ("1h\t",), ("\n1h",), ("1h\n",), ("1 2h",)]),
            mb("empty_and_whitespace_only", [("",), (" ",), ("\t",), ("\n",), (" \r\n\t ",)]),
            mb("non_ascii_digits_and_letters", [("١h",), ("１h",), ("1ｈ",), ("²m",), ("1h٢m",)]),
            mb("type_errors", [(b"5m",), (bytearray(b"5m"),), (5,), (None,), (["5m"],), (1.5,), (b"",)]),
            mb("huge_values_exact", [("123456789012345678901234567890h",), ("99999999999999999999m99999999999999999999s",)]),
            case("str_subclass_is_str",
                 "class S(str):\n    pass\nr = sol.parse_duration(S('1h1m1s'))\nresult = (r, type(r).__name__)"),
        ]
        for k in range(14):
            out.append(mb("random_batch_%02d" % k, [_dur_args(rng) for _ in range(12)]))
        return out


# ---------------------------------------------------------------------------------------------
TPL = "placeholder-template-renderer-with-exact-error-positions"
_NAMECH = set(string.ascii_letters + string.digits + "_")


def _tpl_ref(template, context):
    if not isinstance(template, str):
        raise RefErr("TypeError", "template must be a string")
    if not isinstance(context, dict):
        raise RefErr("TypeError", "context must be a dict")
    out, i, n = [], 0, len(template)
    while i < n:
        ch = template[i]
        if ch == "{" and template[i + 1:i + 2] == "{":
            out.append("{")
            i += 2
        elif ch == "{":
            j = i + 1
            name = ""
            while True:
                if j == n:
                    raise RefErr("ValueError", "unclosed placeholder at position %d" % i)
                c = template[j]
                if c == "}":
                    break
                if c not in _NAMECH:
                    raise RefErr("ValueError", "invalid placeholder at position %d" % i)
                name += c
                j += 1
            if not name:
                raise RefErr("ValueError", "empty placeholder at position %d" % i)
            if name not in context:
                raise RefErr("KeyError", name)
            out.append(str(context[name]))
            i = j + 1
        elif ch == "}" and template[i + 1:i + 2] == "}":
            out.append("}")
            i += 2
        elif ch == "}":
            raise RefErr("ValueError", "stray '}' at position %d" % i)
        else:
            out.append(ch)
            i += 1
    return "".join(out)


_TPL_ATOMS = ["{", "}", "{{", "}}", "{a}", "{b}", "{name}", "{A_1}", "{missing}", "x", " ", "é", "-", "{}", "{a",
              "a}", "{ a}", "{a b}", "{é}", "{١}", "{_}", "{9}", "text", "{{a}}", "\n"]


def _tpl_args(rng, err_bias=0.5):
    if rng.random() < err_bias:
        atoms = _TPL_ATOMS
    else:
        atoms = ["{{", "}}", "{a}", "{b}", "{name}", "{A_1}", "{_}", "{9}", "x", " ", "é", "-", "text", "{{a}}", "\n", "日本"]
    t = "".join(rng.choice(atoms) for _ in range(rng.randint(0, 8)))
    ctx = {"a": rng.choice([1, "A", None, [1, 2], "{b}", 2.5]), "b": "B", "name": "Ana", "A_1": True, "_": "u", "9": 9}
    for k in list(ctx):
        if rng.random() < 0.1:
            del ctx[k]
    r = rng.random()
    if r < 0.03:
        return (rng.choice([None, 5, b"x", ["x"]]), rng.choice([ctx, None]))
    if r < 0.06:
        return (t, rng.choice([None, [("a", 1)], "ctx"]))
    return (t, ctx)


@register(TPL)
class Template:
    note = "reference from the prompt: left-to-right scanner with escape-first rule and position-tagged errors"
    n_cross = 1000

    def brute(template, context):
        return _tpl_ref(template, context)

    def gen(rng):
        return _tpl_args(rng)

    call = staticmethod(_make_call(_tpl_ref))

    def cases(rng):
        mb = lambda name, args: _mixed_batch(name, TPL, "render_template", _tpl_ref, args)  # noqa: E731
        ctx = {"a": 1, "name": "Ana", "x": "X"}
        out = [
            mb("escape_wins_over_placeholder", [("{{a}", ctx), ("{{{a}", ctx), ("{{{{a}}}}", ctx), ("{{a}}}}", ctx)]),
            mb("closing_runs", [("{a}}", ctx), ("{a}}}", ctx), ("}}}", ctx), ("}}}}}", ctx), ("a}}b}", ctx)]),
            mb("stray_brace_positions", [("abc}", ctx), ("{{}", ctx), ("x{a}y}z", ctx), ("日本}", ctx)]),
            mb("unclosed_positions", [("abc{", ctx), ("{{ {", ctx), ("x {name", ctx), ("{a}{", ctx), ("é{a_b9", ctx)]),
            mb("invalid_positions", [("{a{b}}", ctx), ("xy{é}", ctx), ("{١}", ctx), ("{a.b}", ctx), ("{a\n}", ctx),
                                     ("{{x}} {-}", ctx), ("{a }", ctx)]),
            mb("empty_positions", [("ab{}", ctx), ("{{}}{}", ctx), ("{a}{}", ctx)]),
            mb("missing_key_names", [("{nope}", ctx), ("{a}{Name}", ctx), ("{x}{_x9}", ctx), ("{A}", ctx)]),
            mb("scan_order_key_vs_syntax", [("{zz} }", ctx), ("} {zz}", ctx), ("{zz}{", ctx), ("{{ {zz} {-}", ctx),
                                            ("{a}{zz}{}", ctx), ("{}{zz}", ctx)]),
            mb("name_charset", [("{abcXYZ_09}", {"abcXYZ_09": "ok"}), ("{_}", {"_": 0}), ("{0}", {"0": "zero"})]),
            mb("values_not_rerendered", [("{a}", {"a": "{b}"}), ("{a}{b}", {"a": "}", "b": "{"}), ("{a}", {"a": "{{"})]),
            mb("str_of_values", [("{a}|{b}|{c}|{d}", {"a": None, "b": (1, "x"), "c": 1.5, "d": False}),
                                 ("{a}", {"a": {"k": 1}})]),
            mb("argument_types", [(None, {}), (5, None), (b"{a}", {"a": 1}), ("x", None), ("x", [("a", 1)]),
                                  ("", ())]),
            mb("plain_unicode_passthrough", [("héllo wörld 日本 ✓", {}), ("", {}), ("\t\n", {})]),
            case("key_error_str_contains_name",
                 "try:\n    sol.render_template('ok {a} {user_id}', {'a': 1})\n    result = 'no error'\n"
                 "except KeyError as e:\n    result = ('user_id' in str(e), 'KeyError')"),
            case("dict_subclass_context",
                 "class D(dict):\n    pass\nresult = sol.render_template('{a}-{b}', D(a=1, b=2))"),
            case("context_values_str_called",
                 "class V:\n    def __str__(self):\n        return 'S!'\n    def __repr__(self):\n        return 'R!'\n"
                 "result = sol.render_template('<{v}>', {'v': V()})"),
            case("long_template",
                 "parts = []\nctx = {}\nfor i in range(3000):\n    ctx['k%d' % i] = i\n"
                 "    parts.append('{k%d}{{%d}}' % (i, i))\nresult = sol.render_template(''.join(parts), ctx)"),
        ]
        for k in range(14):
            out.append(mb("random_batch_%02d" % k, [_tpl_args(rng, 0.0 if k < 5 else 0.7) for _ in range(12)]))
        return out


# ---------------------------------------------------------------------------------------------
RPN = "rpn-evaluator-with-truncating-division-and-indexed-errors"


def _rpn_ref(tokens):
    if not isinstance(tokens, list):
        raise RefErr("TypeError", "tokens must be a list")
    if tokens == []:
        raise RefErr("ValueError", "empty expression")
    st = []
    for i, t in enumerate(tokens):
        if not isinstance(t, str):
            raise RefErr("TypeError", "token %d" % i)
        if t in ("+", "-", "*", "/"):
            if len(st) < 2:
                raise RefErr("ValueError", "stack underflow at token %d" % i)
            b = st.pop()
            a = st.pop()
            if t == "+":
                st.append(a + b)
            elif t == "-":
                st.append(a - b)
            elif t == "*":
                st.append(a * b)
            else:
                if b == 0:
                    raise RefErr("ZeroDivisionError", "token %d" % i)
                q = abs(a) // abs(b)
                st.append(q if (a >= 0) == (b >= 0) else -q)
            continue
        body = t[1:] if t[:1] in "+-" and t else t
        if body == "" or any(c not in "0123456789" for c in body):
            raise RefErr("ValueError", "unknown token", "token %d" % i)
        v = 0
        for c in body:
            v = v * 10 + "0123456789".index(c)
        st.append(-v if t[0] == "-" else v)
    if len(st) != 1:
        raise RefErr("ValueError", "leftover operands")
    return st[0]


def _rpn_lit(rng):
    v = rng.choice([rng.randint(0, 20), rng.randint(0, 10 ** 6), rng.randint(0, 10 ** 30)])
    s = str(v)
    r = rng.random()
    if r < 0.25:
        s = "-" + s
    elif r < 0.3:
        s = "+" + s
    elif r < 0.35:
        s = "0" + s
    return s


def _rpn_valid(rng, n_ops):
    toks = [_rpn_lit(rng)]
    for _ in range(n_ops):
        toks += [_rpn_lit(rng), rng.choice("+-*//")]
    if rng.random() < 0.3 and len(toks) > 3:  # reorder: push several then fold
        lits = [t for t in toks if t not in "+-*/"]
        ops = [t for t in toks if t in "+-*/"]
        toks = lits + ops
    return toks


def _rpn_args(rng, err_rate=0.45):
    toks = _rpn_valid(rng, rng.choice([0, 1, 2, 3, 5, 8]))
    if rng.random() < err_rate:
        k = rng.randrange(7)
        p = rng.randrange(len(toks) + 1)
        if k == 0:
            toks.insert(p, rng.choice([5, None, 1.5, b"1", True, ["1"]]))
        elif k == 1:
            toks.insert(p, rng.choice(["--4", "1.5", "", " 3", "3 ", "1_000", "+-1", "٣", "x", "%", "**", "//",
                                       "0x10", "1e3", "++", "- 1", "+", "-"]))
        elif k == 2:
            toks.insert(p, rng.choice("+-*/"))
        elif k == 3:
            toks.append(_rpn_lit(rng))
        elif k == 4:
            toks += ["0", "/"]
        elif k == 5:
            toks = toks[:p] + ["0", "/"] + toks[p:]
        else:
            return (rng.choice([[], tuple(toks), " ".join(str(t) for t in toks), None]),)
    return (toks,)


@register(RPN)
class Rpn:
    note = "reference from the prompt: stack machine with manual digit parsing and abs-based truncation"
    n_cross = 1000

    def brute(tokens):
        return _rpn_ref(tokens)

    def gen(rng):
        return _rpn_args(rng)

    call = staticmethod(_make_call(_rpn_ref))

    def cases(rng):
        mb = lambda name, args: _mixed_batch(name, RPN, "eval_rpn", _rpn_ref, args)  # noqa: E731
        big = str(10 ** 40 + 7)
        out = [
            mb("truncation_all_sign_combos", [([a, b, "/"],) for a in ("7", "-7", "1", "-1", "0", "-0", "6", "-6")
                                              for b in ("2", "-2", "3", "-3", "7", "-7")]),
            mb("truncation_huge_exact", [([big, "3", "/"],), (["-" + big, "3", "/"],), ([big, "-" + str(10 ** 20 + 3), "/"],),
                                         (["-" + big, "-" + str(10 ** 20 + 3), "/"],), ([str(2 ** 64 + 1), "-2", "/"],)]),
            mb("sign_literals", [(["+0"],), (["-0"],), (["-5", "-3", "-"],), (["+5", "+5", "*"],), (["000"],),
                                 (["-007", "2", "+"],)]),
            mb("single_operator_strings_are_operators", [(["3", "-"],), (["-"],), (["4", "2", "-", "+"],)]),
            mb("invalid_literal_forms", [(["1_000"],), (["٣"],), (["３"],), (["²"],), (["3 "],), (["1", "\t2", "+"],),
                                         (["+-1"],), (["-+1"],), (["0x10"],), (["1e3"],), (["1.0"],), (["--"],),
                                         (["++"],), (["+ 1"],), (["2", "3", "add"],), (["2", "3", "//"],), (["2", "3", "**"],)]),
            mb("non_str_tokens", [(["1", True],), ([False],), (["1", "2", 3.0],), (["1", b"2", "+"],), ([None, "x"],)]),
            mb("scan_order_errors", [(["x", 5],), ([5, "x"],), (["+", "x"],), (["x", "+"],), (["1", "0", "/", "y"],),
                                     (["1", "0", "/", "+"],), (["1", "+", "0", "/"],), (["1", "2", "x"],), (["1", "2", "3"],),
                                     (["1", "2", "3", "+", "+", "+"],)]),
            mb("index_beyond_nine", [(["1"] * 11 + ["+"] * 10 + ["0", "/"],), (["1"] * 12 + ["bad"],),
                                     (["1", "1", "+"] + ["+"] * 10,), (["1"] * 10 + [7],)]),
            mb("zero_divisor_forms", [(["1", "-0", "/"],), (["1", "+0", "/"],), (["1", "00", "/"],), (["2", "2", "-", "1", "/"],),
                                      (["1", "2", "2", "-", "/"],)]),
            mb("not_list_or_empty", [([],), (("1",),), ("1 2 +",), (None,), ({"1": 1},)]),
            mb("results_and_types", [(["2", "3", "+", "4", "*"],), (["-7", "2", "/"],), (["10", "3", "/", "3", "*"],)]),
            case("long_expression_exact",
                 "toks = ['1']\nfor i in range(2, 2000):\n    toks += [str(i), '*' if i % 5 else '-']\n"
                 "toks += ['-' + '9' * 300, '/']\nr = sol.eval_rpn(toks)\nresult = (r, type(r).__name__)"),
        ]
        for k in range(14):
            out.append(mb("random_batch_%02d" % k, [_rpn_args(rng, 0.0 if k < 5 else 0.7) for _ in range(12)]))
        return out


# ---------------------------------------------------------------------------------------------
DG = "recursive-deep-get-with-loop-ban"


def _dg_ref(data, path):
    if not isinstance(path, str):
        raise RefErr("TypeError", "path must be a string")
    if path == "":
        raise RefErr("ValueError", "path must not be empty")
    segs = path.split(".")
    if "" in segs:
        raise RefErr("ValueError", "empty segment")
    node = data
    for s in segs:
        if isinstance(node, dict):
            if s not in node:
                raise RefErr("KeyError", s)
            node = node[s]
        elif isinstance(node, list):
            body = s[1:] if s.startswith("-") else s
            if body == "" or any(c not in "0123456789" for c in body):
                raise RefErr("ValueError", "invalid index")
            idx = int(s)
            if not -len(node) <= idx < len(node):
                raise RefErr("IndexError", s)
            node = node[idx]
        else:
            raise RefErr("TypeError", "cannot descend")
    return node


_DG_KEYS = ["a", "b", "users", "0", "1", "-1", "x y", "é", "日本", "K", "07", "_"]


def _dg_data(rng, depth=0):
    r = rng.random()
    if depth >= 4 or r < 0.25:
        return rng.choice([1, "s", None, True, 2.5, (1, 2), "", 0, b"b"])
    if r < 0.6:
        return {k: _dg_data(rng, depth + 1) for k in rng.sample(_DG_KEYS, rng.randint(0, 4))}
    return [_dg_data(rng, depth + 1) for _ in range(rng.randint(0, 4))]


def _dg_path(rng, data):
    segs = []
    node = data
    for _ in range(rng.randint(1, 5)):
        if isinstance(node, dict) and node and rng.random() < 0.85:
            k = rng.choice(list(node))
            segs.append(k)
            node = node[k]
        elif isinstance(node, list) and node and rng.random() < 0.85:
            i = rng.randrange(len(node))
            form = rng.random()
            if form < 0.6:
                segs.append(str(i))
            elif form < 0.8:
                segs.append(str(i - len(node)))
            else:
                segs.append("0" + str(i))
            node = node[i]
        else:
            segs.append(rng.choice(["a", "zz", "0", "-1", "5", "-9", "+1", "1.0", "x", "1_0", "٣", "-", "-0", "00"]))
            break
    path = ".".join(segs)
    if rng.random() < 0.06:
        path = rng.choice([path + ".", "." + path, path.replace(".", "..", 1) if "." in path else path + "..x"])
    return path


def _dg_args(rng):
    data = _dg_data(rng)
    if rng.random() < 0.03:
        return (data, rng.choice([None, 5, ["a"], b"a", ""]))
    return (data, _dg_path(rng, data))


def _dg_norm(v):
    return repr(v)


@register(DG)
class DeepGet:
    note = "reference from the prompt: iterative walk with up-front empty-segment check"
    n_cross = 1000

    def brute(data, path):
        return _dg_ref(data, path)

    def gen(rng):
        return _dg_args(rng)

    call = staticmethod(_make_call(_dg_ref, _dg_norm))

    def cases(rng):
        # value checked by repr + identity with the node reached through the reference path
        mb = lambda name, args: _mixed_batch(name, DG, "deep_get", _dg_ref, args, norm_code="repr(_v)",  # noqa: E731
                                             norm=_dg_norm)
        data = {"users": [{"name": "ana", "tags": ["x", "y"]}, {"name": "bob", "tags": []}], "0": "zero",
                "n": {"1": {"-1": "neg-key"}}, "t": (1, 2), "s": "str", "none": None, "x y": {"é": [10, [20, 30]]}}
        out = [
            mb("dict_keys_are_strings", [({0: "int-key", "0": "str-key"}, "0"), ({1: "a"}, "1"), ({True: 1}, "True")]),
            mb("numeric_looking_dict_keys", [(data, "n.1.-1"), (data, "0"), ({"07": 7}, "07"), ({"-1": "m"}, "-1")]),
            mb("negative_and_padded_indexes", [([[1, 2, 3]], "0.-3"), ([[1, 2, 3]], "0.-0"), ([[1, 2, 3]], "0.002"),
                                               ([[1, 2, 3]], "-1.-1"), ([[1, 2, 3]], "0.-03")]),
            mb("index_out_of_range_text", [([[1, 2, 3]], "0.3"), ([[1, 2, 3]], "0.-4"), ([[]], "0.0"),
                                           ([[]], "0.-1"), ([1], "10"), ([1], "0010"), ([1], "-02")]),
            mb("invalid_index_forms", [([1], "+1"), ([1], "1.0"), ([1], "1_0"), ([1], "٣"), ([1], "１"), ([1], " 1"),
                                       ([1], "-"), ([1], "--1"), ([1], "a"), ([1], "1e0"), ([1], "-+1")]),
            mb("cannot_descend_atoms", [(data, "t.0"), (data, "s.0"), (data, "none.x"), (data, "users.0.name.0"),
                                        (5, "a"), (None, "0"), ("abc", "0"), ((1,), "0"), (b"ab", "0"), (1.5, "x")]),
            mb("empty_segment_before_anything", [(5, "a..b"), ([], ".0"), ({}, "a."), (None, "."), ({"a": 1}, "a.b..c"),
                                                 ({"a": 1}, "zz.."), (5, "..")]),
            mb("path_errors_order", [(5, None), ({}, 1), ({}, b"a"), ({}, ["a"]), ({}, ""), (None, "")]),
            mb("unicode_and_space_keys", [(data, "x y.é.1.0"), ({"日本": {"語": 1}}, "日本.語"), ({" ": 1}, " ")]),
            mb("returns_none_and_falsy", [({"a": None}, "a"), ({"a": [0]}, "a.0"), ({"a": ""}, "a"), ({"a": {}}, "a")]),
            mb("missing_keys", [(data, "users.0.age"), (data, "nope"), ({"a": {"b": 1}}, "a.B"), ({}, "x")]),
            case("returns_same_object",
                 "inner = {'k': [1, 2]}\ndata = {'a': [inner]}\n"
                 "result = (sol.deep_get(data, 'a.0') is inner, sol.deep_get(data, 'a.-1.k') is inner['k'])"),
            case("key_error_type_and_segment",
                 "try:\n    sol.deep_get({'a': {'b': 1}}, 'a.missing_seg')\n    result = 'no error'\n"
                 "except KeyError as e:\n    result = ('KeyError', 'missing_seg' in str(e))"),
            case("path_120_segments_mixed",
                 "data = 'leaf'\nsegs = []\nfor i in range(120):\n    if i % 2:\n        data = [None, data]\n"
                 "        segs.append('1' if i % 4 == 1 else '-1')\n    else:\n        data = {'k%d' % i: data}\n"
                 "        segs.append('k%d' % i)\nresult = sol.deep_get(data, '.'.join(reversed(segs)))"),
        ]
        for k in range(14):
            out.append(mb("random_batch_%02d" % k, [_dg_args(rng) for _ in range(12)]))
        return out


# ---------------------------------------------------------------------------------------------
TOPK = "top-k-frequent-without-sorting-builtins"


def _topk_ref(items, k):
    if not isinstance(items, list):
        raise RefErr("TypeError", "items must be a list")
    if isinstance(k, bool) or not isinstance(k, int):
        raise RefErr("TypeError", "k must be an int")
    if k < 0:
        raise RefErr("ValueError", "k must be >= 0")
    cnt, first = {}, {}
    for i, v in enumerate(items):
        cnt[v] = cnt.get(v, 0) + 1
        first.setdefault(v, i)
    order = sorted(cnt, key=lambda v: (-cnt[v], first[v]))
    return [(v, cnt[v]) for v in order[:k]]


_TOPK_POOLS = [
    list("abcdefgh"),
    list(range(-3, 9)),
    ["a", "b", ("t", 1), ("t", 2), None, "é", "日本", "", 7, -7, (), frozenset([1])],
]


def _topk_args(rng, err_rate=0.15):
    pool = rng.choice(_TOPK_POOLS)
    m = rng.randint(1, len(pool))
    sub = pool[:m]
    items = [rng.choice(sub) for _ in range(rng.choice([0, 1, 2, 5, 10, 30, 80]))]
    k = rng.choice([0, 1, 2, 3, rng.randint(0, 15), 100])
    if rng.random() < err_rate:
        kind = rng.choice("ikn")
        if kind == "i":
            items = rng.choice([tuple(items), "abc", None, {"a": 1}])
            if rng.random() < 0.4:
                k = rng.choice([True, -1, 1.0])
        elif kind == "k":
            k = rng.choice([True, False, 1.0, "1", None, 1j])
        else:
            k = rng.choice([-1, -5, -10 ** 20])
    return (items, k)


@register(TOPK)
class TopK:
    note = "reference from the prompt: dict counts + sorted by (-count, first index)"
    n_cross = 800

    def brute(items, k):
        return _topk_ref(items, k)

    def gen(rng):
        return _topk_args(rng)

    call = staticmethod(_make_call(_topk_ref))

    def cases(rng):
        mb = lambda name, args: _mixed_batch(name, TOPK, "top_k_frequent", _topk_ref, args,  # noqa: E731
                                             check_unchanged=True)
        out = [
            mb("single_item", [(["x"], 1), (["x"], 0), (["x"], 5)]),
            mb("all_same", [(["q"] * 9, 1), (["q"] * 9, 3)]),
            mb("later_value_overtakes", [(["a", "b", "b", "c", "c", "c"], 3), (["a", "b", "a", "b", "b"], 1)]),
            mb("tie_break_first_occurrence_not_value", [(["b", "a", "a", "b"], 2), ([3, 2, 1, 1, 2, 3], 3),
                                                        ([10, 2, 2, 10], 1), (["z", "a"], 1)]),
            mb("k_boundaries", [(["a", "b", "c"], 3), (["a", "b", "c"], 2), (["a", "b", "c"], 4), ([], 0), ([], 10 ** 20)]),
            mb("huge_k", [(["a", "b", "a"], 10 ** 30)]),
            mb("mixed_hashables_tuples_none", [([None, ("x", 1), None, "", "", "", ()], 4), ([(), (), frozenset([1])], 2)]),
            mb("bad_items_precedence", [("ab", True), (None, -1), (("a",), 1.0), ({"a": 1}, 1), ({"a"}, 0)]),
            mb("bad_k_variants", [(["a"], True), ([], False), (["a"], 1.0), ([], "2"), (["a"], None), (["a"], 1j)]),
            mb("negative_k", [(["a"], -1), ([], -10 ** 20)]),
            case("result_is_new_list_each_call",
                 "items = ['a', 'b', 'a']\nr1 = sol.top_k_frequent(items, 2)\nr1.append('junk')\n"
                 "r2 = sol.top_k_frequent(items, 2)\nresult = (r2, [type(x).__name__ for x in r2], items)"),
            case("many_distinct_values",
                 "items = []\nfor i in range(300):\n    items += [('v', i)] * ((i * 7) % 11 + 1)\n"
                 "r = sol.top_k_frequent(items, 40)\nresult = (r, [type(x).__name__ for x in r])"),
        ]
        for k in range(14):
            out.append(mb("random_batch_%02d" % k, [_topk_args(rng, 0.0 if k < 9 else 0.6) for _ in range(10)]))
        return out
