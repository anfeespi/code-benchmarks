"""v4-strict specs: optimization.

Stress cases stay inside the stated input domain and at (or below) the sizes the prompt's
performance requirement names; timeouts are >= 10x the canonical's standalone wall time.
"""
import itertools
from collections import Counter

from . import register, case, lit, batch_case, call_case


def _batches(rng, entry, prefix, n_batches, per_batch, make):
    return [batch_case("%s_%02d" % (prefix, k), entry, [make(rng) for _ in range(per_batch)])
            for k in range(n_batches)]


# ---------------------------------------------------------------------------------------------
@register("peak-concurrency-and-its-first-instant")
class PeakLoad:
    note = "brute force: load counted at every integer time in [min s, max e)"

    def brute(intervals):
        lo = min(s for s, _ in intervals)
        hi = max(e for _, e in intervals)
        best, best_t = 0, None
        for t in range(lo, hi):
            load = sum(1 for s, e in intervals if s <= t < e)
            if load > best:
                best, best_t = load, t
        return (best, best_t)

    def gen(rng):
        n = rng.randint(1, 12)
        span = rng.choice([5, 20, 60])
        ivs = []
        for _ in range(n):
            s = rng.randint(0, span)
            ivs.append((s, s + rng.randint(1, rng.choice([1, 3, 15]))))
        return (ivs,)

    def cases(rng):
        out = [
            call_case("single_unit_interval", "peak_load", [(0, 1)]),
            call_case("max_bounds_single", "peak_load", [(0, 10**9)]),
            call_case("top_endpoint", "peak_load", [(10**9 - 1, 10**9)]),
            call_case("all_identical", "peak_load", [(7, 9)] * 6),
            call_case("chain_touching", "peak_load", [(i, i + 1) for i in range(10)]),
            call_case("later_higher_peak", "peak_load", [(0, 2), (5, 9), (6, 8), (7, 8)]),
            call_case("end_equals_other_start_many", "peak_load", [(0, 5)] * 3 + [(5, 6)] * 3),
            call_case("unsorted_input", "peak_load", [(50, 60), (10, 20), (15, 55), (0, 100)]),
            call_case("peak_after_gap", "peak_load", [(0, 1), (10, 12), (11, 13), (11, 12)]),
            call_case("ends_before_starts_same_t", "peak_load", [(0, 4), (0, 4), (4, 8), (4, 8), (3, 5)]),
        ]

        def mk(r):
            n = r.randint(1, 30)
            span = r.choice([10, 50, 1000, 10**9 - 1])
            ivs = []
            for _ in range(n):
                s = r.randint(0, span - 1)
                ivs.append((s, min(10**9, s + r.randint(1, max(1, span // r.choice([1, 4, 20]))))))
            return (ivs,)
        out += _batches(rng, "peak_load", "random_batch", 12, 8, mk)
        out.append(case("stress_all_identical_500k",
                        "result = sol.peak_load([(123, 456)] * 500000)", timeout_s=10))
        out.append(case("stress_touching_chain_500k",
                        "result = sol.peak_load([(i, i + 1) for i in range(500000)])", timeout_s=10))
        out.append(case("stress_spread_full_range_400k",
                        "import random\nr = random.Random(41)\nivs = []\nfor _ in range(400000):\n"
                        "    s = r.randint(0, 10**9 - 2)\n    ivs.append((s, min(10**9, s + r.randint(1, 10**7))))\n"
                        "result = sol.peak_load(ivs)", timeout_s=10))
        return out


# ---------------------------------------------------------------------------------------------
def _edf_feasible(ds, cap):
    """Can jobs with these deadlines all be placed? Fill slots 1, 2, ... in deadline order."""
    for i, d in enumerate(sorted(ds)):
        slot = i // cap + 1
        if slot > d:
            return False
    return True


@register("bounty-scheduling-with-slot-capacity")
class Bounty:
    note = "brute force: every subset of jobs, kept if an earliest-deadline slot filling places it"

    def brute(jobs, cap):
        if cap < 1:
            raise ValueError("cap")
        best = 0
        n = len(jobs)
        for mask in range(1 << n):
            sub = [jobs[i] for i in range(n) if mask >> i & 1]
            if _edf_feasible([d for d, _ in sub], cap):
                best = max(best, sum(p for _, p in sub))
        return best

    def gen(rng):
        n = rng.randint(0, 9)
        dmax = rng.choice([1, 2, 3, 5])
        jobs = [(rng.randint(1, dmax), rng.randint(1, rng.choice([3, 50, 10**6]))) for _ in range(n)]
        cap = rng.choice([1, 1, 2, 3, 8, 0, -1]) if rng.random() < 0.95 else rng.randint(-5, 0)
        return (jobs, cap)

    def cases(rng):
        out = [
            call_case("single_job", "max_bounty", [(1, 5)], 1),
            call_case("cap_max_8_all_fit_slot1", "max_bounty", [(1, i + 1) for i in range(8)], 8),
            call_case("cap_8_one_too_many", "max_bounty", [(1, i + 1) for i in range(9)], 8),
            call_case("far_deadline_all_fit", "max_bounty", [(10**9, 10**6)] * 20, 1),
            call_case("max_bounty_values", "max_bounty", [(1, 10**6), (1, 10**6), (2, 10**6)], 1),
            call_case("late_low_vs_early_high", "max_bounty", [(3, 1), (1, 100), (1, 99), (2, 50), (3, 2)], 1),
            call_case("deadline_exchange", "max_bounty", [(2, 10), (2, 10), (1, 9), (1, 1)], 1),
            call_case("identical_jobs", "max_bounty", [(3, 4)] * 10, 2),
            call_case("unsorted_input", "max_bounty", [(4, 3), (1, 8), (2, 2), (4, 9), (1, 7), (3, 6), (2, 5)], 1),
            call_case("empty_cap_large", "max_bounty", [], 8),
            call_case("cap_zero_empty_jobs_raises", "max_bounty", [], 0),
            call_case("cap_very_negative_raises", "max_bounty", [(1, 1)], -10**9),
        ]

        def mk(r):
            n = r.randint(0, 9)
            dmax = r.choice([1, 2, 3, 5, 10**9])
            jobs = [(r.randint(1, dmax), r.randint(1, r.choice([3, 50, 10**6]))) for _ in range(n)]
            return (jobs, r.choice([1, 2, 3, 8]))
        out += _batches(rng, "max_bounty", "random_batch", 10, 10, mk)
        # performance requirement: 500,000 jobs with deadlines in a narrow band
        out.append(case("stress_band_near_1e9_cap1",
                        "import random\nr = random.Random(51)\n"
                        "jobs = [(10**9 - r.randint(0, 60000), r.randint(1, 10**6)) for _ in range(500000)]\n"
                        "result = sol.max_bounty(jobs, 1)", timeout_s=15))
        out.append(case("stress_band_mid_cap8",
                        "import random\nr = random.Random(52)\n"
                        "jobs = [(r.randint(40000, 50000), r.randint(1, 10**6)) for _ in range(500000)]\n"
                        "result = sol.max_bounty(jobs, 8)", timeout_s=15))
        out.append(case("stress_all_same_deadline_cap1",
                        "import random\nr = random.Random(53)\n"
                        "jobs = [(100000, r.randint(1, 10**6)) for _ in range(500000)]\n"
                        "result = sol.max_bounty(jobs, 1)", timeout_s=15))
        out.append(case("stress_equal_bounties_band",
                        "jobs = [(1000 + (i % 3000), 7) for i in range(500000)]\n"
                        "result = sol.max_bounty(jobs, 2)", timeout_s=15))
        return out


# ---------------------------------------------------------------------------------------------
@register("divisible-pulse-windows-with-bounded-length")
class Pulses:
    note = "brute force: every (start, length) with lo <= length <= hi, sum checked % k"

    def brute(deltas, k, lo, hi):
        n = len(deltas)
        if not (1 <= lo <= hi <= n):
            raise ValueError("band")
        c = 0
        for i in range(n):
            for L in range(lo, hi + 1):
                if i + L <= n and sum(deltas[i:i + L]) % k == 0:
                    c += 1
        return c

    def gen(rng):
        n = rng.randint(1, 14)
        a = rng.choice([1, 3, 10, 10**6])
        xs = [rng.randint(-a, a) for _ in range(n)]
        k = rng.choice([1, 2, 3, 5, 7, 10**9, rng.randint(1, 30)])
        if rng.random() < 0.1:
            lo, hi = rng.randint(-1, n + 2), rng.randint(-1, n + 2)
        else:
            lo = rng.randint(1, n)
            hi = rng.randint(lo, n)
        return (xs, k, lo, hi)

    def cases(rng):
        out = [
            call_case("k_one_counts_whole_band", "count_pulses", [3, -1, 4, 1, -5, 9], 1, 2, 4),
            call_case("full_band_all_lengths", "count_pulses", [1, 2, 3, 4, 5], 5, 1, 5),
            call_case("lo_eq_hi_eq_n", "count_pulses", [4, -4, 8], 4, 3, 3),
            call_case("all_zeros", "count_pulses", [0] * 12, 7, 3, 9),
            call_case("huge_k_needs_zero_sum", "count_pulses", [10**6, -10**6, 10**6, -10**6, 5], 10**9, 1, 5),
            call_case("negative_sum_multiple", "count_pulses", [-6, -3, 3, -9], 6, 1, 2),
            call_case("extreme_values", "count_pulses", [10**6] * 7 + [-10**6] * 7, 10**6, 2, 9),
            call_case("hi_eq_n_lo_one_single", "count_pulses", [7], 3, 1, 1),
            call_case("lo_negative_raises", "count_pulses", [1, 2, 3], 2, -1, 2),
            call_case("lo_zero_hi_zero_raises", "count_pulses", [1, 2, 3], 2, 0, 0),
            call_case("lo_above_len_raises", "count_pulses", [1, 2, 3], 2, 4, 4),
            call_case("hi_above_len_single_raises", "count_pulses", [5], 5, 1, 2),
        ]

        def mk(r):
            n = r.randint(1, 25)
            a = r.choice([1, 5, 10**6])
            xs = [r.randint(-a, a) for _ in range(n)]
            k = r.choice([1, 2, 3, 7, 10**9, r.randint(1, 50)])
            lo = r.randint(1, n)
            return (xs, k, lo, r.randint(lo, n))
        out += _batches(rng, "count_pulses", "random_batch", 10, 10, mk)
        out.append(case("stress_k1_wide_band_1_2m",
                        "import random\nr = random.Random(61)\n"
                        "d = [r.randint(-10**6, 10**6) for _ in range(1200000)]\n"
                        "result = sol.count_pulses(d, 1, 300000, 550000)", timeout_s=20))
        out.append(case("stress_zeros_huge_k_1_2m",
                        "result = sol.count_pulses([0] * 1200000, 10**9, 1, 250000)", timeout_s=20))
        out.append(case("stress_small_alphabet_band_1_2m",
                        "import random\nr = random.Random(62)\n"
                        "d = [r.choice((-1, 0, 1)) for _ in range(1200000)]\n"
                        "result = sol.count_pulses(d, 3, 600000, 850000)", timeout_s=20))
        return out


# ---------------------------------------------------------------------------------------------
@register("longest-echoed-slice")
class Echo:
    note = "brute force: largest L such that two distinct start positions carry the same length-L substring"

    def brute(s):
        n = len(s)
        for L in range(n - 1, 0, -1):
            seen = set()
            for i in range(n - L + 1):
                t = s[i:i + L]
                if t in seen:
                    return L
                seen.add(t)
        return 0

    def gen(rng):
        n = rng.randint(0, 30)
        alpha = rng.choice(["a", "ab", "abc", "abcdefghijklmnopqrstuvwxyz"])
        s = "".join(rng.choice(alpha) for _ in range(n))
        if rng.random() < 0.3 and n:
            i = rng.randint(0, n - 1)
            s = s + s[i:i + rng.randint(1, 8)]
        return (s,)

    def cases(rng):
        alpha = "abcdefghijklmnopqrstuvwxyz"
        out = [
            call_case("alphabet_no_repeat", "longest_echo", alpha),
            call_case("alphabet_twice", "longest_echo", alpha + alpha),
            call_case("single_repeated_letter_far", "longest_echo", "zabcdefghijklmnopqrstuvwxyz"[::-1] + "z"),
            call_case("all_same_1000", "longest_echo", "q" * 1000),
            call_case("period_two", "longest_echo", "ab" * 50),
            call_case("overlap_aba", "longest_echo", "abababa"),
            call_case("repeat_at_ends", "longest_echo", "xyzabcdefxyz"),
            call_case("prefix_suffix_overlap", "longest_echo", "abcabcabca"),
            call_case("three_letters", "longest_echo", "aab"),
        ]

        def mk(r):
            n = r.randint(0, 60)
            a = r.choice(["ab", "abc", alpha])
            s = "".join(r.choice(a) for _ in range(n))
            if r.random() < 0.4 and n:
                i = r.randint(0, n - 1)
                j = r.randint(0, n)
                s = s[:j] + s[i:i + r.randint(1, 15)] + s[j:]
            return (s,)
        out += _batches(rng, "longest_echo", "random_batch", 10, 10, mk)
        # performance requirement: len 150,000 with an answer of several hundred characters
        out.append(case("stress_binary_alphabet_planted_600",
                        "import random\nr = random.Random(71)\n"
                        "s = [r.choice('ab') for _ in range(148800)]\n"
                        "blk = [r.choice('ab') for _ in range(600)]\n"
                        "s[1000:1600] = blk\ns[120000:120600] = blk\n"
                        "result = sol.longest_echo(''.join(s)[:150000])", timeout_s=15))
        out.append(case("stress_overlapping_planted_500",
                        "import random\nr = random.Random(72)\nal = 'abcdefghijklmnopqrstuvwxyz'\n"
                        "p = ''.join(r.choice(al) for _ in range(50))\nrep = p * 11\n"
                        "s = ''.join(r.choice(al) for _ in range(75000)) + rep + ''.join(r.choice(al) for _ in range(74450))\n"
                        "result = sol.longest_echo(s)", timeout_s=15))
        out.append(case("stress_three_copies_spread",
                        "import random\nr = random.Random(73)\nal = 'abc'\n"
                        "blk = ''.join(r.choice(al) for _ in range(350))\n"
                        "parts = [''.join(r.choice(al) for _ in range(49650)) for _ in range(3)]\n"
                        "s = parts[0] + blk + parts[1] + blk + parts[2][:-350] + blk\n"
                        "result = sol.longest_echo(s)", timeout_s=15))
        return out


# ---------------------------------------------------------------------------------------------
@register("parity-locked-divisible-pairs")
class LockedPairs:
    note = "brute force: all i < j pairs, (a + b) % m == 0 and a % 2 == b % 2"

    def brute(values, m):
        if m < 1:
            raise ValueError("m")
        c = 0
        for i in range(len(values)):
            for j in range(i + 1, len(values)):
                a, b = values[i], values[j]
                if (a + b) % m == 0 and (a - b) % 2 == 0:
                    c += 1
        return c

    def gen(rng):
        n = rng.randint(0, 25)
        a = rng.choice([5, 50, 10**12])
        vals = [rng.randint(-a, a) for _ in range(n)]
        m = rng.choice([1, 2, 3, 4, 6, 10, 10**6, rng.randint(1, 40), 0, -3]) if rng.random() < 0.95 else rng.randint(-5, 0)
        return (vals, m)

    def cases(rng):
        out = [
            call_case("m_two_mixed", "count_locked_pairs", [1, 3, 5, 2, 4, -1, -2, 0], 2),
            call_case("m_even_half_residue", "count_locked_pairs", [3, 9, 15, 21, 6, 12, 18], 6),
            call_case("m_odd_half_absent", "count_locked_pairs", [1, 6, 11, 4, 9, 14], 5),
            call_case("zero_residue_both_parities", "count_locked_pairs", [0, 7, 14, 21, -7, -14, 28], 7),
            call_case("max_m_extremes", "count_locked_pairs", [10**12, -10**12, 10**6, -10**6, 999999, -999999, 1], 10**6),
            call_case("m_larger_than_values", "count_locked_pairs", [1, -1, 2, -2, 3, -3, 3], 10**6),
            call_case("two_equal_values", "count_locked_pairs", [4, 4], 8),
            call_case("pair_opposite_parity_only", "count_locked_pairs", [2, 3], 5),
            call_case("all_same_odd_m1", "count_locked_pairs", [5] * 50, 1),
            call_case("m_one_parity_split", "count_locked_pairs", list(range(-10, 11)), 1),
            call_case("empty_m_zero_raises", "count_locked_pairs", [], 0),
            call_case("m_very_negative_raises", "count_locked_pairs", [1, 1], -10**6),
        ]

        def mk(r):
            n = r.randint(0, 40)
            a = r.choice([5, 50, 10**12])
            return ([r.randint(-a, a) for _ in range(n)], r.choice([1, 2, 3, 4, 6, 10, 10**6, r.randint(1, 100)]))
        out += _batches(rng, "count_locked_pairs", "random_batch", 10, 10, mk)
        out.append(case("stress_all_equal_1_5m",
                        "result = sol.count_locked_pairs([10**12] * 1500000, 1000)", timeout_s=15))
        out.append(case("stress_distinct_residues_m1e6",
                        "import random\nr = random.Random(81)\n"
                        "v = [r.randint(-10**12, 10**12) for _ in range(1500000)]\n"
                        "result = sol.count_locked_pairs(v, 10**6)", timeout_s=15))
        out.append(case("stress_m2_mixed_1_5m",
                        "import random\nr = random.Random(82)\n"
                        "v = [r.randint(-10**12, 10**12) for _ in range(1500000)]\n"
                        "result = sol.count_locked_pairs(v, 2)", timeout_s=15))
        out.append(case("stress_m1_1_5m",
                        "v = [(i * 7919) % 1000003 - 500000 for i in range(1500000)]\n"
                        "result = sol.count_locked_pairs(v, 1)", timeout_s=15))
        return out


# ---------------------------------------------------------------------------------------------
@register("recurring-values-over-many-windows")
class Recurring:
    note = "brute force: Counter over each slice, values with count >= 2"

    def brute(data, queries):
        return [sum(1 for c in Counter(data[l:r]).values() if c >= 2) for l, r in queries]

    def gen(rng):
        n = rng.randint(0, 25)
        vals = rng.choice([[0, 1], [1, 2, 3], list(range(-5, 6)), [-10**9, 10**9, 0]])
        data = [rng.choice(vals) for _ in range(n)]
        qs = []
        for _ in range(rng.randint(0, 12)):
            l = rng.randint(0, n)
            qs.append((l, rng.randint(l, n)))
        return (data, qs)

    def cases(rng):
        out = [
            call_case("all_distinct", "recurring_counts", list(range(10)), [(0, 10), (3, 7), (0, 0), (10, 10)]),
            call_case("all_equal_every_range", "recurring_counts", [5] * 6,
                      [(l, r) for l in range(7) for r in range(l, 7)]),
            call_case("extreme_values", "recurring_counts", [10**9, -10**9, 10**9, -10**9, 0],
                      [(0, 5), (1, 4), (0, 3), (2, 5)]),
            call_case("negative_and_zero", "recurring_counts", [0, -1, 0, -1, 1, 1], [(0, 6), (0, 2), (4, 6), (1, 4)]),
            call_case("single_element", "recurring_counts", [3], [(0, 1), (0, 0), (1, 1), (0, 1)]),
            call_case("queries_descending_r", "recurring_counts", [1, 2, 1, 3, 2, 3, 1], [(0, 7), (0, 6), (0, 5), (0, 4), (0, 3)]),
            call_case("pairs_adjacent", "recurring_counts", [1, 1, 2, 2, 3, 3], [(0, 6), (1, 5), (1, 3), (0, 1), (2, 4)]),
            call_case("empty_data_no_queries", "recurring_counts", [], []),
        ]

        def mk(r):
            n = r.randint(0, 40)
            vals = r.choice([[0, 1], [1, 2, 3], list(range(-5, 6)), [-10**9, 10**9, 7]])
            data = [r.choice(vals) for _ in range(n)]
            qs = []
            for _ in range(r.randint(0, 15)):
                l = r.randint(0, n)
                qs.append((l, r.randint(l, n)))
            return (data, qs)
        out += _batches(rng, "recurring_counts", "random_batch", 10, 8, mk)
        out.append(case("stress_all_equal_full_queries",
                        "data = [7] * 150000\nqs = [(i, 150000 - i) for i in range(0, 60000)]\n"
                        "res = sol.recurring_counts(data, qs)\nresult = [len(res), sum(res), res[:5], res[-5:]]",
                        timeout_s=20))
        out.append(case("stress_all_distinct_random_queries",
                        "import random\nr = random.Random(91)\ndata = list(range(150000))\nr.shuffle(data)\n"
                        "qs = []\nfor _ in range(60000):\n    l = r.randint(0, 100000)\n"
                        "    qs.append((l, min(150000, l + r.randint(1, 50000))))\n"
                        "res = sol.recurring_counts(data, qs)\nresult = [len(res), sum(res), max(res)]", timeout_s=20))
        out.append(case("stress_mixed_values_scattered_queries",
                        "import random\nr = random.Random(92)\n"
                        "data = [r.randint(-10**9, 10**9) if r.random() < 0.5 else r.randint(0, 5000) for _ in range(150000)]\n"
                        "qs = []\nfor _ in range(60000):\n    a, b = r.randint(0, 150000), r.randint(0, 150000)\n"
                        "    qs.append((min(a, b), max(a, b)))\n"
                        "res = sol.recurring_counts(data, qs)\nresult = res[::97] + [sum(res)]", timeout_s=20))
        return out


# ---------------------------------------------------------------------------------------------
@register("stable-sensor-stretches")
class Stable:
    note = "brute force: every window, max - min compared to tol"

    def brute(readings, tol):
        n = len(readings)
        c = 0
        for i in range(n):
            for j in range(i, n):
                w = readings[i:j + 1]
                if max(w) - min(w) <= tol:
                    c += 1
        return c

    def gen(rng):
        n = rng.randint(0, 20)
        a = rng.choice([2, 10, 10**9])
        xs = [rng.randint(-a, a) for _ in range(n)]
        tol = rng.choice([0, 1, 2, 5, a, 2 * a, rng.randint(0, 2 * a)])
        return (xs, tol)

    def cases(rng):
        out = [
            call_case("increasing_tol_zero", "count_stable_windows", list(range(10)), 0),
            call_case("increasing_tol_two", "count_stable_windows", list(range(10)), 2),
            call_case("decreasing_tol_three", "count_stable_windows", list(range(10, 0, -1)), 3),
            call_case("alternating", "count_stable_windows", [0, 5] * 6, 4),
            call_case("alternating_fits", "count_stable_windows", [0, 5] * 6, 5),
            call_case("spike_in_middle", "count_stable_windows", [1, 1, 1, 100, 1, 1, 1], 0),
            call_case("extreme_values_tol_huge", "count_stable_windows", [10**9, -10**9, 10**9, -10**9], 2 * 10**9),
            call_case("extreme_values_tol_short", "count_stable_windows", [10**9, -10**9, 0, 10**9], 10**9),
            call_case("single_negative", "count_stable_windows", [-7], 0),
            call_case("empty_tol_zero", "count_stable_windows", [], 0),
            call_case("plateaus", "count_stable_windows", [3, 3, 4, 4, 5, 5, 4, 3], 1),
        ]

        def mk(r):
            n = r.randint(0, 40)
            a = r.choice([2, 10, 10**9])
            return ([r.randint(-a, a) for _ in range(n)], r.choice([0, 1, 3, a, r.randint(0, 2 * a)]))
        out += _batches(rng, "count_stable_windows", "random_batch", 10, 10, mk)
        out.append(case("stress_increasing_large_tol",
                        "result = sol.count_stable_windows(list(range(500000)), 300000)", timeout_s=15))
        out.append(case("stress_decreasing_large_tol",
                        "result = sol.count_stable_windows(list(range(500000, 0, -1)), 400000)", timeout_s=15))
        out.append(case("stress_bounded_noise_all_qualify",
                        "import random\nr = random.Random(101)\n"
                        "xs = [r.randint(-10**9, -10**9 + 1000) for _ in range(500000)]\n"
                        "result = sol.count_stable_windows(xs, 1000)", timeout_s=15))
        out.append(case("stress_slow_walk_huge_tol",
                        "import random\nr = random.Random(102)\nxs = []\nv = 0\n"
                        "for _ in range(500000):\n    v += r.randint(-1, 1)\n    xs.append(v)\n"
                        "result = sol.count_stable_windows(xs, 10**9)", timeout_s=15))
        return out


# ---------------------------------------------------------------------------------------------
@register("triple-dominance-pair-counting")
class Dominance:
    note = "brute force: all i < j pairs checked with seq[i] > 3 * seq[j]"

    def brute(seq):
        return sum(1 for i, j in itertools.combinations(range(len(seq)), 2) if seq[i] > 3 * seq[j])

    def gen(rng):
        n = rng.randint(0, 25)
        a = rng.choice([1, 3, 10, 100, 10**9])
        return ([rng.randint(-a, a) for _ in range(n)],)

    def cases(rng):
        out = [
            call_case("boundary_equal_three_times", "count_dominant_pairs", [3, 1, 6, 2, 9, 3]),
            call_case("boundary_just_above", "count_dominant_pairs", [4, 1, 7, 2, 10, 3]),
            call_case("negative_boundary", "count_dominant_pairs", [-3, -1, -2, -1, -6, -2]),
            call_case("zero_vs_negative", "count_dominant_pairs", [0, -1, 0, -1]),
            call_case("negative_then_zero", "count_dominant_pairs", [-1, 0, -1, 0]),
            call_case("all_equal_positive", "count_dominant_pairs", [5] * 30),
            call_case("all_equal_negative", "count_dominant_pairs", [-5] * 30),
            call_case("extremes", "count_dominant_pairs", [10**9, -10**9, 10**9, 333333333, 333333334, -333333334]),
            call_case("increasing", "count_dominant_pairs", list(range(-20, 21))),
            call_case("decreasing", "count_dominant_pairs", list(range(20, -21, -1))),
        ]

        def mk(r):
            n = r.randint(0, 40)
            a = r.choice([1, 3, 10, 100, 10**9])
            return ([r.randint(-a, a) for _ in range(n)],)
        out += _batches(rng, "count_dominant_pairs", "random_batch", 10, 10, mk)
        out.append(case("stress_all_equal_150k", "result = sol.count_dominant_pairs([7] * 150000)", timeout_s=15))
        out.append(case("stress_small_values_dups_150k",
                        "import random\nr = random.Random(111)\n"
                        "seq = [r.randint(-5, 5) for _ in range(150000)]\nresult = sol.count_dominant_pairs(seq)", timeout_s=15))
        out.append(case("stress_increasing_150k",
                        "result = sol.count_dominant_pairs([-10**9 + 13000 * i for i in range(150000)])", timeout_s=15))
        out.append(case("stress_alternating_sign_150k",
                        "import random\nr = random.Random(112)\n"
                        "seq = [r.randint(1, 10**9) * (1 if i % 2 else -1) for i in range(150000)]\n"
                        "result = sol.count_dominant_pairs(seq)", timeout_s=15))
        return out
