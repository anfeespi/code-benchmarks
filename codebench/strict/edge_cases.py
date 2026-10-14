"""v4-strict specs: edge_cases."""
import bisect
import decimal
import itertools
import math
import unicodedata
from fractions import Fraction

from . import register, case, lit, batch_case, call_case


class _Approx:
    """Float wrapper for the cross-check: equal within the prompt's relative error (1e-12)."""

    def __init__(self, v):
        self.v = v

    def __eq__(self, other):
        if not isinstance(other, _Approx):
            return False
        a, b = self.v, other.v
        if type(a) is not type(b):
            return False
        return a == b or math.isclose(a, b, rel_tol=1e-12, abs_tol=0.0)

    def __repr__(self):
        return "_Approx(%r)" % (self.v,)


# --------------------------------------------------------------------------------------------
@register("competition-ranks-with-ties-and-nan-guard")
class RankScores:
    note = "sort descending + bisect: rank = 1 + count of strictly greater scores"

    def brute(scores):
        for s in scores:
            if s != s:
                raise ValueError("nan")
        neg = sorted(-s for s in scores)  # ascending of negatives
        # number of scores strictly greater than s == number of negatives strictly less than -s
        return [1 + bisect.bisect_left(neg, -s) for s in scores]

    def gen(rng):
        n = rng.randint(0, 12)
        pool = [0, -0.0, 0.0, 1, 1.0, 2, 2.5, -1, -3.25, 10**18, float(10**18), float("inf"), float("-inf")]
        xs = []
        for _ in range(n):
            r = rng.random()
            if r < 0.4:
                xs.append(rng.choice(pool))
            elif r < 0.7:
                xs.append(rng.randint(-5, 5))
            elif r < 0.97:
                xs.append(rng.randint(-20, 20) / 4)
            else:
                xs.append(float("nan"))
        return (xs,)

    def cases(rng):
        out = [
            call_case("two_equal", "rank_scores", [4, 4]),
            call_case("strictly_descending", "rank_scores", [9, 7, 5, 3, 1]),
            call_case("strictly_ascending", "rank_scores", [1, 3, 5, 7, 9]),
            call_case("ties_at_bottom", "rank_scores", [5, 1, 1, 1]),
            call_case("multiple_tie_groups", "rank_scores", [3, 1, 3, 2, 1, 3, 2]),
            call_case("neg_zero_vs_zero_ties", "rank_scores", [0.0, -0.0, 0, -0.0, -1e-300, 1e-300]),
            call_case("int_float_equal_mixed", "rank_scores", [1, 1.0, 2.0, 2, 3, 0.5]),
            call_case("huge_ints", "rank_scores", [10**30, 10**30 + 1, -10**30, 10**30]),
            # plain numeric == : 2**53 + 1 != float(2**53) in Python, so they are distinct scores
            call_case("int_float_exact_compare", "rank_scores", [2**53 + 1, float(2**53), 2**53]),
            call_case("all_negative_floats", "rank_scores", [-0.5, -1.5, -0.25, -1.5]),
            case("inf_and_neg_inf_ties",
                 "inf = float('inf')\nresult = sol.rank_scores([-inf, inf, 1e308, inf, -inf, -1e308])"),
            case("only_infinities", "result = sol.rank_scores([float('-inf'), float('inf')])"),
            case("nan_last_raises", "result = sol.rank_scores([1, 2, 3, float('nan')])", ),
            case("nan_among_infinities_raises",
                 "result = sol.rank_scores([float('inf'), float('nan'), float('-inf')])"),
            case("nan_mutation_free",
                 "xs = [3.0, float('nan')]\ntry:\n    sol.rank_scores(xs)\n    raised = False\n"
                 "except ValueError:\n    raised = True\nresult = (raised, len(xs), xs[0])"),
            case("float_input_not_mutated",
                 "xs = [2.5, -1.0, 2.5, 0.0, -0.0]\nsnap = list(xs)\nr = sol.rank_scores(xs)\n"
                 "result = (xs == snap, [repr(x) for x in xs], r)"),
            case("result_is_list_of_ints",
                 "r = sol.rank_scores([1.5, 2.5, 1.5])\nresult = (type(r).__name__, [type(x).__name__ for x in r], r)"),
        ]
        for k in range(10):
            batch = []
            for _ in range(8):
                n = rng.randint(1, 25)
                xs = []
                for _ in range(n):
                    r = rng.random()
                    if r < 0.5:
                        xs.append(rng.randint(-6, 6))
                    elif r < 0.8:
                        xs.append(rng.randint(-24, 24) / 4)
                    else:
                        xs.append(rng.choice([0, -0.0, 0.0, 10**12, -10**12, 1e-9]))
                batch.append((xs,))
            out.append(batch_case("random_batch_%02d" % k, "rank_scores", batch))
        return out


# --------------------------------------------------------------------------------------------
_MARKS = ["\u0301", "\u0300", "\u0316", "\u0308", "\u093e", "\u0903", "\u0488", "\u20dd", "\ufe0f", "\u05b7"]
_BASES = ["a", "b", "Z", " ", "\u00e9", "\u4e2d", "\U0001F600", "\U0001F1E6", "\u200d", "\u0915", "\n", "1", "\uac00"]


@register("display-width-truncation-with-combining-marks")
class TruncateDisplay:
    note = "index scan: positions of unit starts (non-mark, or first char), slice at start index #width"

    def brute(s, width):
        if width < 0:
            raise ValueError("neg")
        starts = [i for i, ch in enumerate(s)
                  if i == 0 or unicodedata.category(ch) not in ("Mn", "Mc", "Me")]
        if width >= len(starts):
            return s
        return s[:starts[width]]

    def gen(rng):
        n = rng.randint(0, 12)
        s = "".join(rng.choice(_MARKS) if rng.random() < 0.4 else rng.choice(_BASES) for _ in range(n))
        w = rng.randint(-2, n + 2) if rng.random() < 0.1 else rng.randint(0, n + 2)
        return (s, w)

    def cases(rng):
        T = "truncate_display"
        out = [
            call_case("single_base", T, "x", 1),
            call_case("single_base_width_zero", T, "x", 0),
            call_case("only_marks_is_one_unit", T, "\u0301\u0302\u0303", 1),
            call_case("only_marks_width_zero", T, "\u0301\u0302\u0303", 0),
            call_case("leading_marks_then_base", T, "\u0301\u0302ab", 1),
            call_case("leading_marks_width_three", T, "\u0301\u0302ab", 3),
            call_case("enclosing_mark_me", T, "1\u20e3 2\u20e3", 2),
            call_case("devanagari_mc_marks", T, "\u0915\u093e\u0916\u093f\u0917", 2),
            call_case("many_marks_on_one_base", T, "e" + "\u0301" * 30 + "f", 1),
            call_case("hebrew_points", T, "\u05e9\u05b8\u05c1\u05dc\u05d5\u05b9\u05dd", 2),
            call_case("cjk_counts_one_each", T, "\u4e2d\u6587\u5b57", 2),
            call_case("emoji_with_variation_selector", T, "\u2764\ufe0f\u2764\ufe0f", 1),
            # ZWJ (U+200D) is category Cf, not a combining mark: it is its own unit
            call_case("zwj_is_its_own_unit", T, "\U0001F468\u200d\U0001F469", 2),
            call_case("regional_indicators_separate", T, "\U0001F1E8\U0001F1F4\U0001F1FA", 2),
            call_case("precomposed_vs_decomposed", T, "\u00e9e\u0301\u00e9", 2),
            call_case("whitespace_and_newline", T, " \n\t", 2),
            call_case("width_huge", T, "abc\u0301", 10**9),
            call_case("width_exact_units_with_trailing_mark", T, "ab\u0301", 2),
            case("negative_width_on_empty_raises", "result = sol.truncate_display('', -1)"),
            case("negative_width_large_raises", "result = sol.truncate_display('abc', -10**9)"),
            case("width_equal_units_returns_same",
                 "s = 'x\\u0301y\\u0302'\nr = sol.truncate_display(s, 2)\nresult = (r == s, r)"),
        ]
        for k in range(8):
            batch = []
            for _ in range(10):
                n = rng.randint(0, 20)
                s = "".join(rng.choice(_MARKS) if rng.random() < 0.35 else rng.choice(_BASES) for _ in range(n))
                batch.append((s, rng.randint(0, n + 1)))
            out.append(batch_case("random_batch_%02d" % k, T, batch))
        return out


# --------------------------------------------------------------------------------------------
@register("even-chunking-of-arbitrary-iterables")
class ChunkEvenly:
    note = "drain once, then ceil((remaining)/(chunks left)) sizes (longer chunks first)"

    def brute(items, n):
        if n < 1:
            raise ValueError("n")
        it = iter(items)
        buf = []
        for x in it:
            buf.append(x)
        L = len(buf)
        out, pos = [], 0
        for i in range(n):
            # chunk i spans [ceil-ish boundaries]: start = i*L//n adjusted so longer chunks come first
            size = -(-(L - pos) // (n - i))
            out.append(buf[pos:pos + size])
            pos += size
        return out

    def call(fn, args):
        items, n, kind = args
        src = iter(items) if kind == "gen" else (tuple(items) if kind == "tuple" else list(items))
        return fn(src, n)

    def gen(rng):
        L = rng.randint(0, 20)
        items = [rng.choice([1, 2, "a", None, 3.5]) for _ in range(L)]
        n = rng.randint(-1, 25) if rng.random() < 0.1 else rng.randint(1, 25)
        return (items, n, rng.choice(["list", "tuple", "gen"]))

    def cases(rng):
        C = "chunk_evenly"
        out = [
            call_case("single_element_n1", C, [42], 1),
            call_case("n_equals_len", C, [1, 2, 3, 4], 4),
            call_case("n_one_more_than_len", C, [1, 2, 3], 4),
            call_case("n_much_larger", C, ["x", "y"], 9),
            call_case("empty_tuple_n1", C, (), 1),
            call_case("len_one_less_than_multiple", C, list(range(11)), 4),
            call_case("len_one_more_than_multiple", C, list(range(13)), 4),
            call_case("string_iterable", C, "abcdefg", 3),
            call_case("nested_and_unhashable", C, [[1], {"a": 1}, [1], None, (2,)], 3),
            call_case("duplicates_preserved", C, [0, 0, 0, 0, 0], 2),
            case("range_input", "result = sol.chunk_evenly(range(10), 3)"),
            case("generator_more_chunks_than_items",
                 "result = sol.chunk_evenly((c for c in 'ab'), 5)"),
            case("iterator_from_iter", "result = sol.chunk_evenly(iter([5, 6, 7, 8, 9, 10, 11]), 3)"),
            case("dict_keys_view", "result = sol.chunk_evenly({'k1': 0, 'k2': 1, 'k3': 2}.keys(), 2)"),
            case("one_shot_iterable_consumed_once",
                 "class Once:\n    def __init__(self, data):\n        self.data = data\n        self.used = False\n"
                 "    def __iter__(self):\n        if self.used:\n            raise RuntimeError('iterated twice')\n"
                 "        self.used = True\n        return iter(self.data)\n"
                 "result = sol.chunk_evenly(Once(list(range(9))), 4)"),
            case("no_len_iterator",
                 "class NoLen:\n    def __init__(self, k):\n        self.i, self.k = 0, k\n"
                 "    def __iter__(self):\n        return self\n    def __next__(self):\n"
                 "        if self.i >= self.k:\n            raise StopIteration\n        self.i += 1\n        return self.i\n"
                 "result = sol.chunk_evenly(NoLen(10), 4)"),
            case("chunks_are_lists_from_tuple",
                 "r = sol.chunk_evenly((1, 2, 3, 4, 5), 3)\nresult = ([type(c).__name__ for c in r], r)"),
            case("chunks_are_lists_from_string",
                 "r = sol.chunk_evenly('abcde', 2)\nresult = ([type(c).__name__ for c in r], r)"),
            case("n_zero_on_generator_raises", "result = sol.chunk_evenly((x for x in [1, 2]), 0)"),
            case("n_zero_on_empty_raises", "result = sol.chunk_evenly([], 0)"),
            case("n_very_negative_raises", "result = sol.chunk_evenly([1], -10**9)"),
            case("large_generator",
                 "r = sol.chunk_evenly((i for i in range(100003)), 7)\n"
                 "result = ([len(c) for c in r], [c[0] for c in r], [c[-1] for c in r], sum(sum(c) for c in r))"),
        ]
        for k in range(8):
            batch = []
            for _ in range(10):
                L = rng.randint(0, 30)
                batch.append(([rng.randint(0, 9) for _ in range(L)], rng.randint(1, 12)))
            out.append(batch_case("random_batch_%02d" % k, C, batch))
        return out


# --------------------------------------------------------------------------------------------
@register("exact-integer-k-th-root-floor")
class KthRoot:
    note = "Decimal(prec=120) exp(ln(n)/k) estimate, then integer fix-up until r**k <= n < (r+1)**k"

    def brute(n, k):
        if n < 0 or k < 1:
            raise ValueError("bad")
        if n == 0:
            return 0
        with decimal.localcontext() as ctx:
            ctx.prec = 120
            est = (decimal.Decimal(n).ln() / k).exp()
        r = max(0, int(est))
        while r > 0 and r ** k > n:
            r -= 1
        while (r + 1) ** k <= n:
            r += 1
        return r

    def gen(rng):
        mode = rng.random()
        k = rng.choice([1, 2, 3, 4, 5, 7, 10, 20, 64, 199, 200, 1000, rng.randint(1, 300)])
        if mode < 0.05:
            return (rng.randint(-5, -1), k)
        if mode < 0.08:
            return (rng.randint(0, 100), rng.randint(-3, 0))
        if mode < 0.5:
            r = rng.randint(1, 10**rng.randint(1, 20))
            if r ** k > 10**60:
                return (rng.randint(0, 10**60), k)
            return (r ** k + rng.choice([-1, 0, 1]), k)
        return (rng.randint(0, 10**rng.randint(0, 60)), k)

    def cases(rng):
        K = "kth_root_floor"
        out = [
            call_case("max_n_square", K, 10**60, 2),
            call_case("max_n_minus_one_square", K, 10**60 - 1, 2),
            call_case("max_n_k60", K, 10**60, 60),
            call_case("max_n_k61", K, 10**60, 61),
            call_case("max_n_k199", K, 10**60, 199),
            call_case("max_n_k200", K, 10**60, 200),
            call_case("pow2_200_k200", K, 2**200, 200),
            call_case("pow2_199_k200", K, 2**199, 200),
            call_case("k_one_max", K, 10**60, 1),
            call_case("n_one_huge_k", K, 1, 10**6),
            call_case("n_zero_huge_k", K, 0, 10**6),
            call_case("n_two_k2", K, 2, 2),
            call_case("n_three_k2", K, 3, 2),
            call_case("n_four_k2", K, 4, 2),
            call_case("huge_k_on_big_n", K, 10**60, 10**5),
            call_case("near_cube_root_float_trap_below", K, (10**20 - 1) ** 3, 3),
            call_case("near_cube_root_float_trap_minus1", K, (10**20 - 1) ** 3 - 1, 3),
            call_case("near_cube_root_float_trap_plus1", K, (10**20 + 1) ** 3 - 1, 3),
            call_case("square_of_big_prime", K, 999999999999999999989 ** 2, 2),
            call_case("square_of_big_prime_minus1", K, 999999999999999999989 ** 2 - 1, 2),
            call_case("fifth_power_boundary", K, 12345678901 ** 5 - 1, 5),
            case("n_negative_large_raises", "result = sol.kth_root_floor(-10**60, 3)"),
            case("n_negative_k_zero_raises", "result = sol.kth_root_floor(-1, 0)"),
            case("n_zero_k_zero_raises", "result = sol.kth_root_floor(0, 0)"),
            case("result_is_int",
                 "r = sol.kth_root_floor(10**60, 3)\nresult = (type(r).__name__, r)"),
            case("exact_powers_sweep",
                 "out = []\nfor k in (2, 3, 4, 5, 6, 7):\n    r = 10**(60 // k) - 3\n"
                 "    for n in (r**k - 1, r**k, r**k + 1, (r+1)**k - 1, (r+1)**k):\n"
                 "        out.append(sol.kth_root_floor(n, k))\nresult = out"),
        ]
        for k in range(8):
            batch = []
            for _ in range(10):
                kk = rng.choice([2, 3, 4, 5, 6, 7, 8, 9, 11, 13, 17, 30, 59, 61, 100, 197])
                maxr = int(round(10 ** (60 / kk)))
                r = rng.randint(1, max(1, maxr - 1))
                n = r ** kk + rng.choice([-1, 0, 1, rng.randint(0, r)])
                n = max(0, min(n, 10**60))
                batch.append((n, kk))
            out.append(batch_case("random_power_boundaries_%02d" % k, K, batch))
        for k in range(4):
            batch = [(rng.randint(0, 10**60), rng.randint(1, 250)) for _ in range(10)]
            out.append(batch_case("random_uniform_%02d" % k, K, batch))
        return out


# --------------------------------------------------------------------------------------------
@register("largest-remainder-integer-allocation")
class Allocate:
    note = "exact Fraction quotas, floor + remainder ordering by (-remainder, index)"
    n_cross = 800

    def brute(total, weights):
        if total < 0:
            raise ValueError("t")
        if not weights:
            raise ValueError("e")
        if any(w < 0 for w in weights):
            raise ValueError("n")
        W = sum(Fraction(w) for w in weights)
        if W == 0:
            raise ValueError("z")
        q = [Fraction(total) * Fraction(w) / W for w in weights]
        fl = [math.floor(x) for x in q]
        left = total - sum(fl)
        order = sorted(range(len(q)), key=lambda i: (-(q[i] - fl[i]), i))
        for i in order[:left]:
            fl[i] += 1
        return fl

    def gen(rng):
        r = rng.random()
        if r < 0.03:
            return (rng.randint(-5, -1), [1, 2])
        if r < 0.05:
            return (rng.randint(0, 9), [])
        if r < 0.08:
            return (rng.randint(0, 9), [rng.randint(-3, 3) for _ in range(rng.randint(1, 4))])
        n = rng.randint(1, 8)
        weights = [rng.choice([0, 0, rng.randint(1, 10), rng.randint(1, 1000)]) for _ in range(n)]
        if sum(weights) == 0 and rng.random() < 0.7:
            weights[rng.randrange(n)] = 1
        total = rng.choice([0, 1, rng.randint(0, 20), rng.randint(0, 1000), rng.randint(0, 10**6)])
        return (total, weights)

    def cases(rng):
        A = "allocate_shares"
        out = [
            call_case("total_one_single", A, 1, [5]),
            call_case("total_zero_single", A, 0, [5]),
            call_case("total_one_many_equal", A, 1, [3, 3, 3, 3, 3]),
            call_case("total_less_than_parties", A, 3, [1, 1, 1, 1, 1, 1, 1]),
            call_case("zero_weights_between", A, 10, [0, 1, 0, 1, 0, 1, 0]),
            call_case("zero_weight_first_with_tie", A, 1, [0, 1, 1]),
            call_case("larger_remainder_later_index", A, 10, [1, 2]),
            call_case("remainder_order_not_weight_order", A, 10, [7, 3, 5]),
            call_case("tie_break_three_way", A, 5, [2, 2, 2]),
            call_case("tie_break_among_subset", A, 4, [1, 3, 1, 3]),
            call_case("single_party_huge_total", A, 10**6, [0.001]),
            call_case("many_parties_one_unit_each", A, 3, [1] * 10),
            call_case("exact_division_no_leftover", A, 60, [1, 2, 3]),
            call_case("float_weights_halves", A, 3, [0.5, 0.5]),
            call_case("float_weights_mixed", A, 10, [2.5, 1.25, 1.25]),
            call_case("int_and_float_weights", A, 9, [1, 2.0, 0, 1.0]),
            case("sum_is_total_large",
                 "w = [((i * 13) % 7) for i in range(50)]\nr = sol.allocate_shares(9973, w)\n"
                 "result = (sum(r), len(r), r)"),
            case("types_are_int_float_weights",
                 "r = sol.allocate_shares(10, [0.5, 0.25, 0.25])\nresult = ([type(x).__name__ for x in r], r)"),
            case("negative_total_large_raises", "result = sol.allocate_shares(-5, [1])"),
            case("negative_weight_raises_with_positive_sum", "result = sol.allocate_shares(5, [3, -1, 2])"),
            case("negative_float_weight_raises", "result = sol.allocate_shares(5, [1.0, -0.5])"),
            case("all_zero_single_raises", "result = sol.allocate_shares(5, [0])"),
            case("zero_total_zero_sum_raises", "result = sol.allocate_shares(0, [0, 0, 0])"),
        ]
        for k in range(10):
            batch = []
            for _ in range(10):
                n = rng.randint(1, 9)
                w = [rng.choice([0, rng.randint(1, 9), rng.randint(1, 500)]) for _ in range(n)]
                if sum(w) == 0:
                    w[0] = rng.randint(1, 9)
                t = rng.choice([0, 1, rng.randint(0, 50), rng.randint(0, 100000)])
                # skip inputs where float quotas disagree with the exact spec (canonical float issue)
                if _float_alloc(t, w) == Allocate.brute(t, w):
                    batch.append((t, w))
            out.append(batch_case("random_int_weights_%02d" % k, A, batch))
        return out


def _float_alloc(total, weights):
    """Float-quota variant (what the canonical computes); used only to filter out inputs on which
    float rounding breaks an exact remainder tie."""
    W = sum(weights)
    q = [total * w / W for w in weights]
    fl = [math.floor(x) for x in q]
    order = sorted(range(len(q)), key=lambda i: (-(q[i] - fl[i]), i))
    for i in order[:total - sum(fl)]:
        fl[i] += 1
    return fl


# --------------------------------------------------------------------------------------------
_SPY = (
    "import itertools\n"
    "class Spy:\n"
    "    def __init__(self, src, limit=None):\n"
    "        self.src = iter(src)\n"
    "        self.taken = 0\n"
    "        self.limit = limit\n"
    "    def __iter__(self):\n"
    "        return self\n"
    "    def __next__(self):\n"
    "        if self.limit is not None and self.taken >= self.limit:\n"
    "            raise RuntimeError('over-advanced')\n"
    "        v = next(self.src)\n"
    "        self.taken += 1\n"
    "        return v\n"
)


@register("lazy-round-robin-interleaver")
class RoundRobin:
    note = "itertools.zip_longest with a sentinel, sentinel dropped (finite inputs)"

    def brute(iterables):
        sent = object()
        return [x for tup in itertools.zip_longest(*iterables, fillvalue=sent) for x in tup if x is not sent]

    def call(fn, args):
        lists, kinds = args
        its = []
        for lst, kd in zip(lists, kinds):
            if kd == "gen":
                its.append((x for x in lst))
            elif kd == "str":
                its.append("".join(lst))
            else:
                its.append(list(lst))
        return list(fn(its))

    def gen(rng):
        m = rng.randint(0, 6)
        lists, kinds = [], []
        for _ in range(m):
            kd = rng.choice(["list", "gen", "str"])
            L = rng.choice([0, 0, 1, rng.randint(0, 8)])
            if kd == "str":
                lists.append([rng.choice("abcxyz") for _ in range(L)])
            else:
                lists.append([rng.randint(0, 5) for _ in range(L)])
            kinds.append(kd)
        return (lists, kinds)

    def cases(rng):
        out = [
            case("single_list", "result = list(sol.round_robin([[1, 2, 3]]))"),
            case("single_string", "result = list(sol.round_robin(['hello']))"),
            case("single_empty", "result = list(sol.round_robin([[]]))"),
            case("empty_first_then_values", "result = list(sol.round_robin([[], 'ab', [], [1]]))"),
            case("tuple_and_range_inputs", "result = list(sol.round_robin([(1, 2), range(10, 13), iter([7])]))"),
            case("unicode_string_chars", "result = list(sol.round_robin(['\u00e9\u4e2d', 'x\U0001F600']))"),
            case("none_values_preserved", "result = list(sol.round_robin([[None, None], [0, None]]))"),
            case("short_first_long_last", "result = list(sol.round_robin([[1], [], [2, 3, 4, 5]]))"),
            case("empty_input_next_raises_stopiteration",
                 "it = sol.round_robin([])\ntry:\n    next(it)\n    result = 'no stop'\nexcept StopIteration:\n    result = 'stop'"),
            case("all_empty_iterator_protocol",
                 "it = sol.round_robin([[], ''])\nresult = (iter(it) is it, list(it))"),
            case("generators_mixed_finite_infinite",
                 "import itertools\nresult = list(itertools.islice(sol.round_robin([(x for x in 'ab'), itertools.count(5), [9]]), 8))"),
            case("infinite_repeat_with_finite",
                 "import itertools\nresult = list(itertools.islice(sol.round_robin([itertools.repeat('r'), [1, 2]]), 7))"),
            case("islice_zero_from_infinite",
                 "import itertools\nresult = list(itertools.islice(sol.round_robin([itertools.count()]), 0))"),
            case("call_does_not_advance_inputs",
                 _SPY + "a = Spy(itertools.count(), limit=0)\nb = Spy([1, 2], limit=0)\n"
                 "it = sol.round_robin([a, b])\nresult = (a.taken, b.taken)"),
            case("first_value_advances_only_first_input",
                 _SPY + "a = Spy(itertools.count(), limit=1)\nb = Spy(itertools.count(100), limit=0)\n"
                 "it = sol.round_robin([a, b])\nv = next(it)\nresult = (v, a.taken, b.taken)"),
            case("prefix_advance_counts",
                 _SPY + "spies = [Spy(itertools.count(0)), Spy('abc'), Spy(itertools.count(100))]\n"
                 "vals = list(itertools.islice(sol.round_robin(spies), 5))\n"
                 "result = (vals, [s.taken for s in spies])"),
            case("over_advance_fuse_infinite",
                 _SPY + "a = Spy(itertools.count(0), limit=3)\nb = Spy(itertools.count(50), limit=3)\n"
                 "c = Spy(itertools.count(90), limit=2)\n"
                 "vals = list(itertools.islice(sol.round_robin([a, b, c]), 8))\n"
                 "result = (vals, a.taken, b.taken, c.taken)"),
            case("over_advance_fuse_after_dropout",
                 _SPY + "a = Spy([1], limit=None)\nb = Spy(itertools.count(10), limit=4)\n"
                 "vals = list(itertools.islice(sol.round_robin([a, b]), 5))\n"
                 "result = (vals, a.taken, b.taken)"),
            case("incremental_next_counts",
                 _SPY + "spies = [Spy(itertools.count(0)), Spy(itertools.count(10)), Spy(itertools.count(20))]\n"
                 "it = sol.round_robin(spies)\nlog = []\nfor _ in range(4):\n    v = next(it)\n"
                 "    log.append((v, [s.taken for s in spies]))\nresult = log"),
            case("many_infinite_inputs",
                 "import itertools\nresult = list(itertools.islice(sol.round_robin([itertools.count(i * 1000) for i in range(50)]), 120))"),
            case("large_finite_mixed",
                 "srcs = [list(range(i)) for i in range(60)]\nr = list(sol.round_robin(srcs))\n"
                 "result = (len(r), r[:80], r[-10:])"),
        ]
        for k in range(8):
            batch = []
            for _ in range(10):
                m = rng.randint(0, 6)
                batch.append([[rng.randint(0, 9) for _ in range(rng.choice([0, 1, rng.randint(0, 7)]))]
                              for _ in range(m)])
            code = "result = [list(sol.round_robin(x)) for x in %s]" % lit(batch)
            out.append(case("random_batch_%02d" % k, code))
        return out


# --------------------------------------------------------------------------------------------
@register("lower-weighted-median-with-tolerance")
class WeightedMedian:
    note = "group by distinct value, cumulative per distinct value with float sum, threshold W/2 - 1e-9"

    def brute(values, weights):
        if len(values) != len(weights):
            raise ValueError("len")
        if any(w < 0 for w in weights):
            raise ValueError("neg")
        W = sum(weights)
        if not values or W <= 0:
            raise ValueError("W")
        th = W / 2 - 1e-9
        for v in sorted(set(values)):
            c = sum(w for x, w in zip(values, weights) if x <= v)
            if c >= th:
                return v
        raise AssertionError("unreachable")

    def gen(rng):
        r = rng.random()
        if r < 0.03:
            return ([1, 2], [1])
        if r < 0.05:
            return ([], [])
        if r < 0.08:
            n = rng.randint(1, 4)
            return ([rng.randint(0, 3) for _ in range(n)], [rng.choice([0, 1, -1]) for _ in range(n)])
        n = rng.randint(1, 10)
        vals = [rng.randint(-5, 5) for _ in range(n)]
        # integer / dyadic weights keep float sums exact so the order of summation cannot matter
        ws = [rng.choice([0, 0.0, 1, 2, 0.5, 0.25, 3.0, rng.randint(0, 5)]) for _ in range(n)]
        return (vals, ws)

    def cases(rng):
        M = "weighted_median"
        out = [
            call_case("two_equal_weights_lower", M, [5, 9], [1, 1]),
            call_case("heavy_last", M, [1, 2, 3], [1, 1, 5]),
            call_case("heavy_first", M, [1, 2, 3], [5, 1, 1]),
            call_case("unsorted_with_heavy_middle", M, [30, 10, 20], [1, 1, 3]),
            call_case("zero_weight_smallest_value", M, [-100, 1, 2], [0, 1, 1]),
            call_case("zero_weight_leading_and_trailing", M, [0, 5, 6, 99], [0.0, 2.0, 2.0, 0.0]),
            call_case("duplicate_values_split_weight", M, [2, 1, 2, 3], [1, 2, 1, 4]),
            call_case("duplicates_cross_half", M, [4, 4, 1, 9], [1, 1, 1, 1]),
            call_case("single_with_zero_others", M, [3, 8, 1], [0, 7.5, 0]),
            call_case("negative_floats", M, [-1.5, -2.5, -0.5], [1, 1, 1]),
            call_case("all_identical_values_float", M, [2.5, 2.5], [0.1, 0.2]),
            call_case("decimal_weights_tolerance", M, [1, 2, 3], [0.1, 0.2, 0.3]),
            # cumulative 1.0 vs W/2 = 1.000000000001: within the 1e-9 tolerance -> reaches
            call_case("within_tolerance_reaches", M, [1, 2], [1.0, 1.000000000002]),
            # cumulative 1.0 vs W/2 = 1.000000002: beyond the tolerance -> does not reach
            call_case("beyond_tolerance_does_not_reach", M, [1, 2], [1.0, 1.000000004]),
            call_case("tiny_weights", M, [1, 2, 3], [1e-12, 1e-12, 1e-12]),
            call_case("large_weights", M, [1, 2, 3], [1e15, 1e15, 2e15 + 4]),
            call_case("single_negative_value", M, [-42], [0.5]),
            case("length_mismatch_longer_weights_raises", "result = sol.weighted_median([1], [1, 1])"),
            case("length_mismatch_empty_values_raises", "result = sol.weighted_median([], [1.0])"),
            case("negative_weight_with_positive_total_raises",
                 "result = sol.weighted_median([1, 2, 3], [5.0, -0.5, 1.0])"),
            case("all_zero_int_weights_raises", "result = sol.weighted_median([1, 2, 3], [0, 0, 0])"),
            case("result_is_input_value",
                 "vals = [0.1, 0.7, 0.3]\nr = sol.weighted_median(vals, [1, 1, 1])\nresult = (r in vals, r)"),
            case("inputs_not_reordered_matter",
                 "a = sol.weighted_median([3, 1, 2], [1, 1, 1])\nb = sol.weighted_median([1, 2, 3], [1, 1, 1])\n"
                 "c = sol.weighted_median([2, 3, 1], [1, 1, 1])\nresult = (a, b, c)"),
        ]
        for k in range(8):
            batch = []
            for _ in range(10):
                n = rng.randint(1, 15)
                vals = [rng.randint(-20, 20) for _ in range(n)]
                ws = [rng.choice([0, 1, 2, 3, 0.5, 0.25, 1.5]) for _ in range(n)]
                if sum(ws) == 0:
                    ws[rng.randrange(n)] = 1
                batch.append((vals, ws))
            out.append(batch_case("random_batch_%02d" % k, M, batch))
        return out


# --------------------------------------------------------------------------------------------
def _exact_norm(v):
    s = sum(Fraction(x) ** 2 for x in v)
    if s == 0:
        return 0.0
    with decimal.localcontext() as ctx:
        ctx.prec = 60
        ctx.Emin = -999999
        ctx.Emax = 999999
        d = (decimal.Decimal(s.numerator) / decimal.Decimal(s.denominator)).sqrt()
        return float(d)


@register("overflow-safe-euclidean-norm")
class VectorNorm:
    note = "exact Fraction sum of squares + 60-digit Decimal sqrt, compared at rel 1e-12"

    def brute(v):
        for x in v:
            if math.isnan(x) or math.isinf(x):
                raise ValueError("nf")
        return _exact_norm(v)

    def call(fn, args):
        return _Approx(fn(*args))

    def gen(rng):
        n = rng.randint(0, 8)
        e = rng.choice([-300, -200, -150, -10, 0, 10, 150, 200, 300])
        v = []
        for _ in range(n):
            r = rng.random()
            if r < 0.1:
                v.append(0.0)
            elif r < 0.15:
                v.append(-0.0)
            elif r < 0.6:
                v.append(rng.uniform(-10, 10) * 10.0 ** e)
            else:
                v.append(rng.uniform(-10, 10) * 10.0 ** rng.choice([e, e - 5, -300, 300, 0]))
        if rng.random() < 0.05 and v:
            v[rng.randrange(len(v))] = rng.choice([float("nan"), float("inf"), float("-inf")])
        # stay within the representable range of the result
        if all(math.isfinite(x) for x in v) and v:
            if sum(Fraction(x) ** 2 for x in v) >= Fraction(1.7e308) ** 2:
                v = [x / 16 for x in v]
        return (v,)

    def cases(rng):
        out = []

        def scaled(name, vec_code, scale_exp):
            # result divided by a power of ten so tiny/huge values are compared at full precision
            out.append(case(name, "v = %s\nresult = sol.vector_norm(v) / 1e%d" % (vec_code, scale_exp)))

        scaled("single_huge", "[1e308]", 308)
        scaled("single_negative_huge", "[-1.5e308]", 308)
        scaled("two_huge_near_max", "[1e308, 1e307]", 308)
        scaled("pythagorean_tiny", "[-3e-300, 4e-300]", -300)
        scaled("min_normal", "[2.2250738585072014e-308, 2.2250738585072014e-308]", -308)
        scaled("many_huge_terms", "[1e300] * 100", 301)
        scaled("many_tiny_terms", "[1e-300] * 10000", -298)
        scaled("huge_and_tiny_mixed", "[1e-300, 3e200, 1e-300, -4e200]", 200)
        scaled("tiny_dominates_zero", "[0.0, -0.0, 7e-250]", -250)
        out.append(case("single_value", "result = sol.vector_norm([2.5])"))
        out.append(case("single_negative", "result = sol.vector_norm([-0.125])"))
        out.append(case("negative_zero_only", "r = sol.vector_norm([-0.0])\nresult = (type(r).__name__, r)"))
        out.append(case("single_zero_is_float", "r = sol.vector_norm([0.0])\nresult = (type(r).__name__, r)"))
        out.append(case("nonzero_returns_float",
                        "r = sol.vector_norm([3e200, 4e200])\nresult = (type(r).__name__, r / 1e200)"))
        out.append(case("cancellation_free_ones", "result = sol.vector_norm([1.0] * 10000)"))
        out.append(case("accuracy_1e12_moderate",
                        "result = sol.vector_norm([1.0, 1e-8])"))
        out.append(case("nan_only_raises", "result = sol.vector_norm([float('nan')])"))
        out.append(case("inf_only_raises", "result = sol.vector_norm([float('inf')])"))
        out.append(case("neg_inf_last_raises", "result = sol.vector_norm([0.0, 1e300, -float('inf')])"))
        out.append(case("nan_after_huge_raises", "result = sol.vector_norm([1e308, 1e308, float('nan')])"))
        out.append(case("inf_with_zeros_raises", "result = sol.vector_norm([0.0, float('inf'), 0.0])"))
        for k in range(8):
            exps, vecs = [], []
            for _ in range(8):
                e = rng.choice([-300, -250, -200, -100, 0, 100, 200, 250, 300])
                n = rng.randint(1, 10)
                v = [round(rng.uniform(-9.99, 9.99), 6) * 10.0 ** rng.choice([e, e, e - 3, max(e - 40, -300)]) for _ in range(n)]
                v[0] = round(rng.uniform(1, 9.99), 6) * 10.0 ** e
                if abs(_exact_norm(v)) >= 1.7e308:
                    continue
                vecs.append(v)
                exps.append(int(math.floor(math.log10(_exact_norm(v)))))
            code = ("vecs = %s\nexps = %s\nresult = [sol.vector_norm(v) / 10.0 ** e if -300 <= e <= 300 "
                    "else sol.vector_norm(v) * 10.0 ** (-e) for v, e in zip(vecs, exps)]" % (lit(vecs), lit(exps)))
            out.append(case("random_scaled_batch_%02d" % k, code))
        return out
