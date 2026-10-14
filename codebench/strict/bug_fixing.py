"""v4-strict specs: bug_fixing.

Each prompt describes the intended behavior (Contract) of a buggy function; the strict cases
test only that contract.
"""
import copy
import string

from . import register, case, lit, batch_case, call_case


def _names(rng, k, pool="abcdefgh"):
    return [rng.choice(pool) + rng.choice(["", "x", "_1"]) for _ in range(k)]


# --------------------------------------------------------------------------- build order
BUILD_CHECK = """deps = %s
try:
    r = sol.resolve_build_order(deps)
    pos = {p: i for i, p in enumerate(r)}
    result = ('ok', sorted(r), len(r),
              all(d in pos and p in pos and pos[d] < pos[p] for p, ds in deps.items() for d in ds),
              r == sol.resolve_build_order(deps), r == sol.resolve_build_order(%s))
except ValueError:
    result = 'ValueError'"""


def _build_validity(fn, args):
    (deps,) = args
    try:
        r = fn(copy.deepcopy(deps))
    except ValueError:
        return "ValueError"
    pos = {p: i for i, p in enumerate(r)}
    return ("ok", sorted(r), len(r),
            all(d in pos and p in pos and pos[d] < pos[p] for p, ds in deps.items() for d in ds),
            r == fn(copy.deepcopy(deps)))


@register("build-order-resolver-reports-phantom-dependency-cycles")
class BuildOrder:
    note = "Kahn's algorithm (in-degree peeling); cycle iff not every node peeled; compared on validity"

    def brute(deps):
        nodes = set(deps)
        for ds in deps.values():
            nodes |= set(ds)
        need = {n: set(deps.get(n, [])) for n in nodes}
        order = []
        while need:
            ready = sorted(n for n, s in need.items() if not s)
            if not ready:
                raise ValueError("cycle")
            for n in ready:
                order.append(n)
                del need[n]
            for s in need.values():
                s.difference_update(ready)
        return order

    def call(fn, args):
        return _build_validity(fn, args)

    def gen(rng):
        return (_rand_deps(rng, rng.randint(0, 9), cyc=rng.random() < 0.35),)

    def cases(rng):
        out = []

        def add(name, deps):
            out.append(case(name, BUILD_CHECK % (lit(deps), lit(deps))))

        add("diamond_shared_dep", {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []})
        add("shared_dep_only_in_lists", {"x": ["base"], "y": ["base"], "z": ["base", "x", "y"]})
        add("many_dependents_one_base", {"p%02d" % i: ["core"] for i in range(30)})
        add("dependency_only_packages", {"app": ["lib1", "lib2", "lib3"]})
        add("duplicate_entries_shared", {"a": ["c", "c", "b"], "b": ["c", "c"], "c": []})
        add("single_package_no_deps", {"solo": []})
        add("self_dependency_among_valid", {"a": ["b"], "b": [], "c": ["c"]})
        add("cycle_via_dependency_only_key", {"a": ["b"], "b": ["c"], "c": ["a"]})
        add("long_cycle", {"n%d" % i: ["n%d" % ((i + 1) % 12)] for i in range(12)})
        add("cycle_reached_from_shared", {"top": ["m1", "m2"], "m1": ["x"], "m2": ["x"], "x": ["y"], "y": ["x"]})
        add("chain_depth_60", {"c%03d" % i: ["c%03d" % (i + 1)] for i in range(60)})
        add("wide_lattice", {"l%d_%d" % (lv, j): ["l%d_%d" % (lv + 1, k) for k in range(5)]
                             for lv in range(5) for j in range(5)})
        add("unicode_names", {"app": ["n\u00facleo", "\u7f51\u7edc"], "\u7f51\u7edc": ["n\u00facleo"]})
        add("keys_out_of_order", {"z": ["a"], "m": ["z", "a"], "a": []})
        for k in range(12):
            deps = _rand_deps(rng, rng.randint(4, 14), cyc=(k % 3 == 2), dense=True)
            add("random_dag_%02d" % k if k % 3 != 2 else "random_maybe_cycle_%02d" % k, deps)
        return out


def _rand_deps(rng, n, cyc=False, dense=False):
    names = ["p%d" % i for i in range(n + 3)]
    deps = {}
    for i in range(n):
        ds = []
        for _ in range(rng.randint(0, 4 if dense else 3)):
            j = rng.randint(i + 1, n + 2)
            ds.append(names[j])
        if rng.random() < 0.2 and ds:
            ds.append(ds[0])
        deps[names[i]] = ds
    if cyc and n >= 1:
        i = rng.randrange(n)
        j = rng.randint(0, i)
        deps[names[i]] = deps[names[i]] + [names[j]]
    keys = list(deps)
    rng.shuffle(keys)
    return {k: deps[k] for k in keys}


# --------------------------------------------------------------------------- ledger
def _amount_cents(a):
    digits = set("0123456789")
    if "." in a:
        whole, _, frac = a.partition(".")
        if not (1 <= len(frac) <= 2) or not all(c in digits for c in frac):
            raise ValueError
    else:
        whole, frac = a, ""
    if not whole or not all(c in digits for c in whole):
        raise ValueError
    cents = 0
    for c in whole:
        cents = cents * 10 + (ord(c) - 48)
    cents *= 100
    if frac:
        cents += (ord(frac[0]) - 48) * 10 + ((ord(frac[1]) - 48) if len(frac) == 2 else 0)
    if cents <= 0:
        raise ValueError
    return cents


VALID_AMOUNTS = ["0.01", "0.1", "0.10", "0.99", "1", "1.0", "1.00", "1.5", "007", "007.70", "0.07", "100.01",
                 "8.87", "2.67", "70.07", "0.57", "1.13", "4.35", "1234567.89", "99999999999999999999.99",
                 "0.3", "19.99", "00.01", "5.05"]
INVALID_AMOUNTS = ["", ".", "1.", ".5", "3.", "1.234", "12.345", "1e2", "1E2", "-3", "+3", "-0.5", " 1", "1 ",
                   "1\n", "\t2", "1_000", "1,00", "1.2.3", "0", "0.0", "0.00", "000", "00.00", "abc", "1a",
                   "0x10", "inf", "nan", "NaN", "1.-5", "1. 5", "..5", "5..", "1/2", "\u00bd"]


def _tx_trace(fn, args):
    (txs,) = args
    before = copy.deepcopy(txs)
    try:
        r = fn(txs)
    except ValueError:
        return ("ValueError", txs == before)
    return (dict(r), txs == before)


@register("ledger-balances-drift-by-one-cent")
class Ledger:
    note = "manual ASCII-digit parse of whole/fraction to exact cents, then net per account"
    # Unicode decimal digits ("\u0663", "\uff11") are excluded from the inputs: the canonical's
    # re \d accepts them although the prompt requires ASCII digits (reported, not tested).

    def brute(txs):
        bal = {}
        for tx in txs:
            c = _amount_cents(tx["amount"])
            bal[tx["from"]] = bal.get(tx["from"], 0) - c
            bal[tx["to"]] = bal.get(tx["to"], 0) + c
        return bal

    def call(fn, args):
        return _tx_trace(fn, args)

    def gen(rng):
        accts = ["a", "b", "c", "d"]
        txs = []
        for _ in range(rng.randint(0, 6)):
            f, t = rng.sample(accts, 2)
            r = rng.random()
            if r < 0.08:
                amt = rng.choice(INVALID_AMOUNTS)
            elif r < 0.3:
                amt = rng.choice(VALID_AMOUNTS)
            else:
                amt = _rand_amount(rng)
            txs.append({"from": f, "to": t, "amount": amt})
        return (txs,)

    def cases(rng):
        out = []
        code_valid = ("out = []\nfor a in %s:\n    out.append((a, sol.compute_balances([{'from': 'x', 'to': 'y', 'amount': a}])))\n"
                      "result = out")
        out.append(case("valid_amounts_exact", code_valid % lit(VALID_AMOUNTS)))
        drift = ["%d.%02d" % (w, c) for w in (0, 1, 2, 4, 8, 16, 64, 1000) for c in range(0, 100) if w or c]
        out.append(case("all_cent_values_no_drift", code_valid % lit(drift)))
        code_inv = ("out = []\nfor a in %s:\n    try:\n        sol.compute_balances([{'from': 'x', 'to': 'y', 'amount': a}])\n"
                    "        out.append((a, 'accepted'))\n    except ValueError:\n        out.append((a, 'ValueError'))\nresult = out")
        for i in range(0, len(INVALID_AMOUNTS), 12):
            out.append(case("invalid_amounts_%d" % (i // 12), code_inv % lit(INVALID_AMOUNTS[i:i + 12])))
        out.append(call_case("empty_transactions", "compute_balances", []))
        out.append(call_case("net_zero_three_way", "compute_balances",
                             [{"from": "a", "to": "b", "amount": "1.01"}, {"from": "b", "to": "c", "amount": "1.01"},
                              {"from": "c", "to": "a", "amount": "1.01"}]))
        out.append(call_case("unicode_account_names", "compute_balances",
                             [{"from": "Jos\u00e9", "to": "\u674e\u96f7", "amount": "3.33"},
                              {"from": "\u674e\u96f7", "to": "Jos\u00e9", "amount": "0.3"}]))
        out.append(case("invalid_later_record_raises",
                        "txs = [{'from': 'a', 'to': 'b', 'amount': '1.00'}, {'from': 'b', 'to': 'c', 'amount': '1e2'}]\n"
                        "try:\n    sol.compute_balances(txs)\n    result = 'accepted'\nexcept ValueError:\n    result = 'ValueError'"))
        out.append(case("input_not_mutated",
                        "txs = [{'from': 'a', 'to': 'b', 'amount': '0.29'}, {'from': 'b', 'to': 'a', 'amount': '7'}]\n"
                        "import copy\nbefore = copy.deepcopy(txs)\nr = sol.compute_balances(txs)\nresult = (r, txs == before)"))
        code_rand = ("import copy\nout = []\nfor txs in %s:\n    before = copy.deepcopy(txs)\n    try:\n"
                     "        out.append((sol.compute_balances(txs), txs == before))\n    except ValueError:\n"
                     "        out.append(('ValueError', txs == before))\nresult = out")
        for k in range(12):
            batch = []
            for _ in range(6):
                (txs,) = Ledger.gen(rng)
                txs = txs + [{"from": "q", "to": "r", "amount": _rand_amount(rng)}]
                batch.append(txs)
            out.append(case("random_batch_%02d" % k, code_rand % lit(batch)))
        return out


def _rand_amount(rng):
    w = rng.choice([0, rng.randint(0, 9), rng.randint(0, 10**6), rng.randint(0, 10**15)])
    form = rng.randint(0, 2)
    if form == 0:
        w = max(w, 1)
        return "0" * rng.randint(0, 1) + str(w)
    if form == 1:
        f = rng.randint(1 if w == 0 else 0, 9)
        return "%d.%d" % (w, f)
    f = rng.randint(1 if w == 0 else 0, 99)
    return "%d.%02d" % (w, f)


# --------------------------------------------------------------------------- memoize
def _ref_memoize(func):
    store = []  # list of (args, kwargs-dict, result), linear search: equality semantics only

    def wrapper(*args, **kwargs):
        for a, k, r in store:
            if a == args and k == kwargs:
                wrapper.hits += 1
                return r
        wrapper.misses += 1
        r = func(*args, **kwargs)
        store.append((args, dict(kwargs), r))
        return r
    wrapper.hits = 0
    wrapper.misses = 0
    return wrapper


def _memo_trace(memoize, args):
    (script,) = args
    calls = []

    def f(*a, **k):
        calls.append((a, tuple(sorted(k.items()))))
        if a and a[0] == "boom" and len(calls) % 2 == 1:
            raise KeyError("boom")
        return ("v", len(calls), a, tuple(sorted(k.items())))
    w = memoize(f)
    outs = []
    for a, k in script:
        try:
            outs.append(w(*a, **dict(k)))
        except KeyError:
            outs.append("KeyError")
    return outs, w.hits, w.misses, calls


MEMO_RUN = """calls = []
@sol.memoize
def f(*a, **k):
    calls.append((a, tuple(sorted(k.items()))))
    if a and a[0] == 'boom' and len(calls) %% 2 == 1:
        raise KeyError('boom')
    return ('v', len(calls), a, tuple(sorted(k.items())))
outs = []
for a, k in %s:
    try:
        outs.append(f(*a, **dict(k)))
    except KeyError:
        outs.append('KeyError')
result = (outs, f.hits, f.misses, calls)"""


@register("memoization-decorator-returns-results-for-the-wrong-keyword-")
class Memoize:
    note = "reference decorator with a linear list of (args, kwargs dict) entries compared by equality"

    def brute(func):
        return _ref_memoize(func)

    def call(fn, args):
        return _memo_trace(fn, args)

    def gen(rng):
        return (_memo_script(rng, rng.randint(1, 12)),)

    def cases(rng):
        out = []

        def add(name, script):
            out.append(case(name, MEMO_RUN % lit(script)))

        add("kw_order_permutations", [((), (("a", 1), ("b", 2), ("c", 3))), ((), (("c", 3), ("a", 1), ("b", 2))),
                                      ((), (("b", 2), ("c", 3), ("a", 1)))])
        add("same_keys_different_values", [((2,), (("tier", "gold"),)), ((2,), (("tier", "silver"),)),
                                           ((2,), (("tier", "gold"),)), ((2,), (("tier", "silver"),))])
        add("same_values_different_keys", [((), (("a", 1),)), ((), (("b", 1),)), ((), (("a", 1),))])
        add("positional_vs_keyword_tuple_collision", [((("a", 1),), ()), ((), (("a", 1),)), ((("a", 1),), ())])
        add("args_tuple_vs_kwargs_split", [((1, ("k", 2)), ()), ((1,), (("k", 2),)), ((1,), (("k", 2),))])
        add("extra_kwarg_is_new_entry", [((1,), ()), ((1,), (("x", None),)), ((1,), ()), ((1,), (("x", None),))])
        add("positional_order_matters", [((1, 2), ()), ((2, 1), ()), ((1, 2), ())])
        add("no_args_call", [((), ()), ((), ()), ((), ())])
        add("raise_then_success_kw", [(("boom",), (("t", 1),)), (("boom",), (("t", 1),)), (("boom",), (("t", 1),))])
        add("none_and_tuple_values", [((None,), (("k", (1, 2)),)), ((None,), (("k", (1, 2)),)), ((None,), (("k", (2, 1)),))])
        add("unicode_kw_values", [((), (("tier", "or\u00f8"),)), ((), (("tier", "\u91d1"),)), ((), (("tier", "or\u00f8"),))])
        out.append(case("pricing_bug_report",
                        "@sol.memoize\ndef price_for(qty, tier='silver'):\n    return qty * {'silver': 10, 'gold': 25}[tier]\n"
                        "out = [price_for(2, tier='silver'), price_for(2, tier='gold'), price_for(2), price_for(2, tier='gold'),"
                        " price_for(qty=2, tier='gold'), price_for(tier='gold', qty=2)]\n"
                        "result = (out, price_for.hits, price_for.misses)"))
        out.append(case("recursive_fib_counters",
                        "@sol.memoize\ndef fib(n):\n    return n if n < 2 else fib(n - 1) + fib(n - 2)\n"
                        "a = fib(30)\nb = fib(30)\nresult = (a, b, fib.hits, fib.misses)"))
        out.append(case("independent_counters_two_funcs",
                        "@sol.memoize\ndef f(x, y=0):\n    return x + y\n@sol.memoize\ndef g(x, y=0):\n    return x - y\n"
                        "out = [f(1, y=2), g(1, y=2), f(y=2, x=1), f(1, y=2), g(1, 2)]\n"
                        "result = (out, f.hits, f.misses, g.hits, g.misses)"))
        out.append(case("exception_type_propagates_kw",
                        "n = []\n@sol.memoize\ndef f(x, mode='a'):\n    n.append(1)\n    if mode == 'bad':\n        raise ZeroDivisionError('x')\n"
                        "    return x\nr = []\nfor _ in range(3):\n    try:\n        f(1, mode='bad')\n    except ZeroDivisionError:\n"
                        "        r.append('ZeroDivisionError')\nr.append(f(1, mode='a'))\nr.append(f(1, mode='a'))\n"
                        "result = (r, f.hits, f.misses, len(n))"))
        out.append(case("counters_are_int",
                        "@sol.memoize\ndef f(x, *, k=0):\n    return x\nf(1, k=1); f(1, k=1); f(1)\n"
                        "result = (type(f.hits).__name__, type(f.misses).__name__, f.hits, f.misses)"))
        for k in range(12):
            add("random_script_%02d" % k, _memo_script(rng, rng.randint(8, 25)))
        return out


def _memo_script(rng, n):
    keys = ["a", "b", "tier"]
    vals = [0, 1, 2, "gold", "silver", None, (1, 2)]
    pos_pool = [(), (1,), (2,), (1, 2), ("boom",), (("a", 1),), ("gold",)]
    script = []
    for _ in range(n):
        if script and rng.random() < 0.35:
            a, k = rng.choice(script)
            k = list(k)
            rng.shuffle(k)
            script.append((a, tuple(k)))
            continue
        a = rng.choice(pos_pool)
        ks = rng.sample(keys, rng.randint(0, 3))
        script.append((a, tuple((x, rng.choice(vals)) for x in ks)))
    return script


# --------------------------------------------------------------------------- patch applier
def _hunks_brute(lines, hunks):
    n = len(lines)
    for s, d, _ in hunks:
        if s < 0 or s + d > n:
            raise ValueError("range")
    for i in range(len(hunks)):
        for j in range(i + 1, len(hunks)):
            s1, d1, _ = hunks[i]
            s2, d2, _ = hunks[j]
            if s1 == s2 or (s1 < s2 + d2 and s2 < s1 + d1):
                raise ValueError("conflict")
    ins = {s: (d, ins_) for s, d, ins_ in hunks}
    out, i = [], 0
    while i <= n:
        if i in ins:
            d, x = ins[i]
            out.extend(x)
            if d:
                i += d
                continue
        if i < n:
            out.append(lines[i])
        i += 1
    return out


def _hunks_trace(fn, args):
    lines, hunks = args
    lc, hc = copy.deepcopy(lines), copy.deepcopy(hunks)
    try:
        r = fn(lines, hunks)
    except ValueError:
        return ("ValueError", lines == lc, hunks == hc)
    return (r, r is not lines, lines == lc, hunks == hc)


HUNK_RUN = """import copy
out = []
for lines, hunks in %s:
    lc, hc = copy.deepcopy(lines), copy.deepcopy(hunks)
    try:
        r = sol.apply_hunks(lines, hunks)
        out.append((r, r is not lines, lines == lc, hunks == hc))
    except ValueError:
        out.append(('ValueError', lines == lc, hunks == hc))
result = out"""


@register("patch-applier-lands-hunks-on-the-wrong-lines")
class Patch:
    note = "pairwise validity/conflict checks, then rebuild by walking original indices"

    def brute(lines, hunks):
        return _hunks_brute(lines, hunks)

    def call(fn, args):
        return _hunks_trace(fn, args)

    def gen(rng):
        return _rand_patch(rng, valid_bias=rng.random() < 0.6)

    def cases(rng):
        out = []

        def add(name, items):
            out.append(case(name, HUNK_RUN % lit(items)))

        doc = ["l%d" % i for i in range(8)]
        add("early_insert_shifts_later", [(doc, [(1, 0, ["A", "B", "C"]), (5, 1, ["Z"])])])
        add("early_delete_shifts_later", [(doc, [(0, 3, []), (6, 2, ["END"])])])
        add("reverse_order_supply", [(doc, [(7, 1, ["x"]), (4, 2, ["y"]), (0, 1, [])])])
        add("insert_at_end_and_touching", [(doc, [(6, 2, ["T"]), (8, 0, ["APP"])])])
        add("delete_everything", [(doc, [(0, 8, [])]), (doc, [(0, 4, []), (4, 4, [])])])
        add("replace_everything", [(["a"], [(0, 1, ["b", "c"])])])
        add("pure_insert_before_delete_same_region", [(doc, [(2, 0, ["I"]), (3, 2, ["R"])])])
        add("insert_where_delete_ends", [(doc, [(1, 2, ["R"]), (3, 0, ["I"])])])
        add("same_start_insert_and_delete_conflict", [(doc, [(2, 0, ["I"]), (2, 1, ["R"])])])
        add("same_start_two_deletes_conflict", [(doc, [(3, 1, ["a"]), (3, 1, ["b"])])])
        add("insertion_inside_delete_range_conflict", [(doc, [(1, 3, ["R"]), (2, 0, ["I"])])])
        add("overlap_far_apart_in_list", [(doc, [(5, 2, []), (0, 1, []), (2, 1, []), (6, 1, [])])])
        add("out_of_range_start_negative", [(doc, [(-1, 0, ["x"])]), (doc, [(-1, 1, [])])])
        add("out_of_range_past_end", [(doc, [(9, 0, ["x"])]), (doc, [(7, 2, [])]), ([], [(1, 0, ["a"])])])
        add("zero_delete_zero_insert_hunks", [(doc, [(3, 0, []), (5, 0, [])])])
        add("duplicate_lines_and_unicode", [(["\u00e9", "\u00e9", "\U0001f600", ""], [(1, 1, ["\u00e9\u0301"]), (3, 1, ["", ""])])])
        add("empty_hunks_copy", [(["a", "b", "c"], []), ([], [])])
        for k in range(12):
            add("random_batch_%02d" % k, [_rand_patch(rng, valid_bias=(k % 4 != 3)) for _ in range(6)])
        return out


def _rand_patch(rng, valid_bias=True):
    n = rng.randint(0, 10)
    lines = ["L%d" % rng.randint(0, 5) for _ in range(n)]
    hunks = []
    if valid_bias:
        pos = 0
        while pos <= n and rng.random() < 0.8:
            s = rng.randint(pos, n)
            d = rng.randint(0, n - s)
            hunks.append((s, d, ["h%d_%d" % (len(hunks), j) for j in range(rng.randint(0, 3))]))
            pos = s + max(d, 1)
        if rng.random() < 0.2 and hunks:
            s, d, x = rng.choice(hunks)
            hunks.append((s + rng.randint(-1, 1), rng.randint(0, 2), ["dup"]))
    else:
        for _ in range(rng.randint(1, 4)):
            s = rng.randint(-1, n + 1)
            hunks.append((s, rng.randint(0, 3), ["r%d" % j for j in range(rng.randint(0, 2))]))
    rng.shuffle(hunks)
    return (lines, hunks)


# --------------------------------------------------------------------------- merge settings
def _merge_brute(defaults, overrides):
    out = {}
    for k in defaults:
        out[k] = defaults[k]
    for k in overrides:
        o = overrides[k]
        if k in out and type(o) is dict and type(out[k]) is dict:
            out[k] = _merge_brute(out[k], o)
        else:
            out[k] = o
    return out


MERGE_RUN = """import copy
out = []
for d, o in %s:
    dc, oc = copy.deepcopy(d), copy.deepcopy(o)
    r = sol.merge_settings(d, o)
    out.append((r, type(r).__name__, r is not d and r is not o, d == dc, o == oc))
result = out"""


@register("recursive-settings-merger-drops-falsy-overrides")
class Merge:
    note = "recursive two-pass merge (copy defaults, then apply overrides; dict+dict recurse)"

    def brute(d, o):
        return _merge_brute(d, o)

    def call(fn, args):
        d, o = copy.deepcopy(args[0]), copy.deepcopy(args[1])
        dc, oc = copy.deepcopy(d), copy.deepcopy(o)
        r = fn(d, o)
        return (r, r is not d and r is not o, d == dc, o == oc)

    def gen(rng):
        return (_rand_cfg(rng, 3), _rand_cfg(rng, 3, falsy=True))

    def cases(rng):
        out = []

        def add(name, items):
            out.append(case(name, MERGE_RUN % lit(items)))

        add("all_falsy_overrides", [({"a": True, "b": 1, "c": "x", "d": [1], "e": {"k": 1}, "f": 2.5},
                                     {"a": False, "b": 0, "c": "", "d": [], "f": 0.0, "e": None})])
        add("falsy_new_keys_added", [({}, {"a": False, "b": 0, "c": "", "d": [], "e": None, "f": {}})])
        add("empty_dict_override_merges", [({"a": {"x": 1}}, {"a": {}}), ({"a": 1}, {"a": {}})])
        add("dict_replaced_by_falsy_scalar", [({"a": {"x": 1}}, {"a": 0}), ({"a": {"x": 1}}, {"a": False}),
                                               ({"a": {"x": 1}}, {"a": []})])
        add("lists_replace_not_merge", [({"l": [1, 2, 3]}, {"l": [9]}), ({"l": [{"a": 1}]}, {"l": [{"b": 2}]})])
        add("deep_nested_falsy", [({"a": {"b": {"c": {"d": True, "e": 1}}}}, {"a": {"b": {"c": {"d": False}}}})])
        add("override_only_keys_nested", [({"a": 1}, {"b": {"c": {"d": None}}})])
        add("both_empty_and_defaults_only", [({}, {}), ({"a": {"b": 0}}, {}), ({}, {"a": 0})])
        add("unicode_keys_and_values", [({"cl\u00e9": "d\u00e9faut", "\u540d": {"x": 1}}, {"\u540d": {"x": 0}, "cl\u00e9": ""})])
        add("no_mutation_deep", [({"db": {"opts": {"ssl": True}}, "k": [1]}, {"db": {"opts": {"ssl": False, "n": 0}}, "k": []})])
        for k in range(12):
            add("random_batch_%02d" % k, [(_rand_cfg(rng, 3), _rand_cfg(rng, 3, falsy=True)) for _ in range(5)])
        return out


def _rand_cfg(rng, depth, falsy=False):
    keys = ["a", "b", "c", "d"]
    cfg = {}
    for k in rng.sample(keys, rng.randint(0, 4)):
        r = rng.random()
        if depth > 0 and r < 0.35:
            cfg[k] = _rand_cfg(rng, depth - 1, falsy)
        elif falsy and r < 0.7:
            cfg[k] = rng.choice([False, 0, "", [], None, 0.0, {}])
        else:
            cfg[k] = rng.choice([True, 1, 7, "s", [1, 2], 3.5, "x"])
    return cfg


# --------------------------------------------------------------------------- room booking
def _booking_brute(bookings, new):
    s, e = new
    if not s < e:
        raise ValueError("empty")
    group = [b for b in bookings if b[0] < e and s < b[1]]
    keep = [b for b in bookings if not (b[0] < e and s < b[1])]
    if group:
        s = min([s] + [b[0] for b in group])
        e = max([e] + [b[1] for b in group])
    return sorted(keep + [(s, e)])


BOOK_RUN = """out = []
for b, n in %s:
    bc = list(b)
    try:
        r = sol.insert_booking(b, n)
        out.append((r, [type(x).__name__ for x in r], type(r).__name__, r is not b, b == bc))
    except ValueError:
        out.append(('ValueError', b == bc))
result = out"""


@register("room-booking-insert-wrongly-merges-back-to-back-reservations")
class Booking:
    note = "filter overlapping group with the half-open overlap predicate, merge, re-sort"

    def brute(bookings, new):
        return _booking_brute(bookings, new)

    def call(fn, args):
        b, n = list(args[0]), args[1]
        bc = list(b)
        r = fn(b, n)
        return (list(r), [type(x).__name__ for x in r], b == bc)

    def gen(rng):
        return _rand_booking(rng)

    def cases(rng):
        out = []

        def add(name, items):
            out.append(case(name, BOOK_RUN % lit(items)))

        add("touch_both_sides", [([(0, 2), (4, 6)], (2, 4)), ([(0, 2), (2, 4), (4, 6)], (2, 4))])
        add("touch_left_only_overlap_right", [([(0, 2), (3, 6)], (2, 4))])
        add("contained_inside_existing", [([(0, 10)], (3, 4)), ([(0, 10)], (0, 10))])
        add("covers_all", [([(1, 2), (2, 3), (3, 4)], (0, 5)), ([(1, 2), (2, 3), (3, 4)], (1, 4))])
        add("overlap_chain_with_touching_neighbors", [([(0, 1), (1, 3), (4, 6), (6, 9), (9, 10)], (2, 7))])
        add("insert_at_front_and_back_touching", [([(5, 6), (6, 7)], (4, 5)), ([(5, 6), (6, 7)], (7, 8))])
        add("same_as_existing", [([(1, 3), (5, 7)], (5, 7))])
        add("negative_and_float_times", [([(-5, -2), (-2, 0.5)], (-3.5, -2)), ([(0.25, 0.5)], (0.5, 0.75))])
        add("invalid_new_raises", [([(1, 2)], (3, 3)), ([(1, 2)], (5, 4)), ([], (0, 0)), ([], (2.5, 1))])
        add("empty_schedule", [([], (0, 1)), ([], (-10, 10))])
        for k in range(12):
            add("random_batch_%02d" % k, [_rand_booking(rng) for _ in range(6)])
        return out


def _rand_booking(rng):
    b, t = [], rng.randint(-3, 3)
    for _ in range(rng.randint(0, 7)):
        t += rng.choice([0, 0, 1, 2, 3])
        d = rng.randint(1, 4)
        b.append((t, t + d))
        t += d
    s = rng.randint(-4, t + 3)
    e = s + rng.choice([rng.randint(1, 6), rng.randint(1, 6), 0, -1] if rng.random() < 0.1 else [rng.randint(1, 6)])
    if rng.random() < 0.15:
        b = [(x + 0.5, y + 0.5) for x, y in b]
    return (b, (s, e))


# --------------------------------------------------------------------------- session purge
PURGE_RUN = """out = []
for s, now in %s:
    same = s
    keep = {k: v for k, v in s.items() if v > now}
    r = sol.purge_expired(s, now)
    out.append((r, sorted(s.items()), s is same, list(s) == list(keep)))
result = out"""


@register("session-purge-crashes-and-keeps-just-expired-sessions")
class Purge:
    note = "collect ids with expiry <= now in iteration order, compare remaining dict"

    def brute(sessions, now):
        removed = []
        for k in list(sessions):
            if not sessions[k] > now:
                removed.append(k)
        for k in removed:
            sessions.pop(k)
        return removed

    def call(fn, args):
        s = dict(args[0])
        same = s
        r = fn(s, args[1])
        return (r, sorted(s.items()), s is same)

    def gen(rng):
        return _rand_sessions(rng)

    def cases(rng):
        out = []

        def add(name, items):
            out.append(case(name, PURGE_RUN % lit(items)))

        add("all_expired_equal_now", [({"a": 3, "b": 3, "c": 3}, 3)])
        add("none_expired", [({"a": 4, "b": 9}, 3.999)])
        add("float_int_equality", [({"a": 2.0, "b": 2, "c": 2.0000001}, 2)])
        add("negative_times", [({"a": -5, "b": -1, "c": 0}, -1)])
        add("single_session", [({"only": 0}, 0), ({"only": 1}, 0)])
        add("unicode_ids", [({"s\u00e9ance": 1, "\u4f1a\u8bdd": 5, "\U0001f511": 1}, 1)])
        add("interleaved_order_preserved", [({"k%02d" % i: (i * 7) % 5 for i in range(30)}, 2)])
        out.append(case("repeat_purge_idempotent",
                        "s = {'a': 1, 'b': 5, 'c': 3}\nr1 = sol.purge_expired(s, 3)\nr2 = sol.purge_expired(s, 3)\n"
                        "r3 = sol.purge_expired(s, 5)\nresult = (r1, r2, r3, s)"))
        out.append(case("large_store_10k",
                        "s = {('s%05d' % i): (i * 37) % 1000 for i in range(10000)}\nr = sol.purge_expired(s, 499)\n"
                        "result = (len(r), r[:5], r[-5:], len(s), min(s.values()))"))
        for k in range(12):
            add("random_batch_%02d" % k, [_rand_sessions(rng) for _ in range(6)])
        return out


def _rand_sessions(rng):
    s = {}
    for i in range(rng.randint(0, 9)):
        v = rng.randint(0, 10)
        if rng.random() < 0.2:
            v += 0.5
        s["id%d" % rng.randint(0, 20)] = v
    now = rng.randint(-1, 11) + (0.5 if rng.random() < 0.2 else 0)
    return (s, now)


# --------------------------------------------------------------------------- rate limiter
class _RefLimiter:
    def __init__(self, max_calls, window_seconds):
        self.max_calls = max_calls
        self.window = window_seconds
        self.admitted = []

    def allow(self, t):
        live = [s for s in self.admitted if not (t - s >= self.window)]
        self.admitted = live
        if len(live) < self.max_calls:
            self.admitted.append(t)
            return True
        return False

    @property
    def calls(self):
        return self.admitted


def _rl_trace(cls, args):
    m, w, ts = args
    rl = cls(m, w)
    steps = []
    for t in ts:
        ok = rl.allow(t)
        steps.append((ok, list(rl.calls)))
    return steps


RL_RUN = """out = []
for m, w, ts in %s:
    rl = sol.RateLimiter(m, w)
    steps = []
    for t in ts:
        ok = rl.allow(t)
        steps.append((ok, list(rl.calls), type(rl.calls).__name__))
    out.append((steps, rl.max_calls, rl.window))
result = out"""


@register("sliding-window-rate-limiter-admits-one-extra-call")
class RateLimit:
    note = "reference limiter recomputing the live admitted set from the expiry rule each call"

    def brute(m, w):
        return _RefLimiter(m, w)

    def call(fn, args):
        return _rl_trace(fn, args)

    def gen(rng):
        return _rand_rl(rng)

    def cases(rng):
        out = []

        def add(name, items):
            out.append(case(name, RL_RUN % lit(items)))

        add("burst_same_timestamp", [(3, 10, [5, 5, 5, 5, 5, 15, 15, 15, 15])])
        add("limit_one_boundary", [(1, 1, [0, 0.5, 1, 1, 2, 2.999, 3])])
        add("denied_calls_never_count", [(2, 10, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])])
        add("exact_expiry_boundaries", [(2, 5, [0, 5, 5, 10, 10, 10, 14.999, 15])])
        add("large_limit", [(50, 1, [0] * 60 + [1] * 60)])
        add("float_window", [(2, 0.25, [0.0, 0.1, 0.2, 0.25, 0.3, 0.5, 0.75])])
        add("long_gaps_prune_all", [(3, 2, [0, 1, 1, 100, 1000, 1000, 1000, 1000])])
        add("first_call_large_timestamp", [(1, 3, [10**9, 10**9 + 2, 10**9 + 3])])
        for k in range(12):
            add("random_batch_%02d" % k, [_rand_rl(rng) for _ in range(5)])
        return out


def _rand_rl(rng):
    m = rng.randint(1, 5)
    w = rng.choice([1, 2, 3, 5, 10, 2.5, 0.5])
    t = rng.choice([0, 0, 3, 7.5])
    ts = []
    for _ in range(rng.randint(1, 25)):
        t += rng.choice([0, 0, 0.5, 1, 1, 2, 3, w, w])
        ts.append(t)
    return (m, w, ts)
