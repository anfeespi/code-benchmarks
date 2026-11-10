"""v4-strict specs: algorithms."""
import itertools
import math

from . import register, case, batch_case, call_case


# ---------------------------------------------------------------- cheapest walk
@register("cheapest-walk-with-color-switch-surcharge")
class MinCostRoute:
    note = "Bellman-Ford fixpoint over (node, color of last edge) states"

    def brute(n, edges, s, t, switch_cost):
        if s == t:
            return 0
        INF = float("inf")
        dist = {}
        for u, v, w, col in edges:
            for a, b in ((u, v), (v, u)):
                if a == s and w < dist.get((b, col), INF):
                    dist[(b, col)] = w
        changed = True
        while changed:
            changed = False
            for (node, col), d in list(dist.items()):
                for u, v, w, col2 in edges:
                    for a, b in ((u, v), (v, u)):
                        if a != node:
                            continue
                        nd = d + w + (switch_cost if col2 != col else 0)
                        if nd < dist.get((b, col2), INF):
                            dist[(b, col2)] = nd
                            changed = True
        best = min((d for (node, _), d in dist.items() if node == t), default=INF)
        return -1 if best == INF else best

    def gen(rng):
        n = rng.randint(1, 7)
        cols = rng.choice([["r"], ["r", "g"], ["r", "g", "b"], ["a", "A", "é"]])
        edges = []
        for _ in range(rng.randint(0, 12)):
            edges.append((rng.randrange(n), rng.randrange(n), rng.choice([0, 1, 2, 5, 9, 30]), rng.choice(cols)))
        return (n, edges, rng.randrange(n), rng.randrange(n), rng.choice([0, 1, 3, 10, 100]))

    def cases(rng):
        f = "min_cost_route"
        out = [
            call_case("self_loop_only_unreachable", f, 2, [(0, 0, 1, "a")], 0, 1, 5),
            call_case("s_eq_t_with_edges", f, 3, [(0, 1, 5, "a"), (1, 2, 1, "b")], 2, 2, 7),
            call_case("zero_weight_edges", f, 4, [(0, 1, 0, "a"), (1, 2, 0, "a"), (2, 3, 0, "b")], 0, 3, 4),
            call_case("switch_back_and_forth", f, 4, [(0, 1, 1, "a"), (1, 2, 1, "b"), (2, 3, 1, "a")], 0, 3, 3),
            call_case("case_sensitive_colors", f, 3, [(0, 1, 1, "Red"), (1, 2, 1, "red")], 0, 2, 50),
            call_case("unicode_colors", f, 3, [(0, 1, 2, "café"), (1, 2, 2, "café"), (0, 2, 3, "ß")], 0, 2, 0),
            call_case("long_color_names", f, 3, [(0, 1, 1, "blue"), (1, 2, 1, "blue-green")], 0, 2, 4),
            # a self-loop recolors the walk: 0-1 (a), loop at 1 (b), 1-2 (b) => switch once
            call_case("self_loop_recolors_walk", f, 3, [(0, 1, 1, "a"), (1, 1, 1, "b"), (1, 2, 1, "b")], 0, 2, 10),
            # revisiting a node with a different color is needed
            call_case("revisit_node_other_color", f, 4,
                      [(0, 1, 1, "x"), (1, 2, 1, "y"), (2, 1, 1, "x"), (1, 3, 1, "x"), (0, 3, 100, "z")], 0, 3, 1000),
            call_case("max_weights", f, 3, [(0, 1, 10**6, "a"), (1, 2, 10**6, "b")], 0, 2, 10**6),
            call_case("isolated_target_large_n", f, 10000, [(0, 1, 1, "a")], 0, 9999, 1),
        ]
        for k in range(10):
            batch = [MinCostRoute.gen(rng) for _ in range(10)]
            out.append(batch_case("random_batch_%02d" % k, f, batch))
        for k in range(3):
            batch = []
            for _ in range(5):
                n = rng.randint(5, 40)
                cols = ["c%d" % i for i in range(rng.randint(1, 5))]
                edges = [(rng.randrange(n), rng.randrange(n), rng.randint(0, 50), rng.choice(cols))
                         for _ in range(rng.randint(n, 4 * n))]
                batch.append((n, edges, rng.randrange(n), rng.randrange(n), rng.choice([0, 5, 40])))
            out.append(batch_case("random_medium_%02d" % k, f, batch))
        out.append(case("stress_max_random", (
            "import random\nrnd = random.Random(7)\nn = 10000\n"
            "edges = [(rnd.randrange(n), rnd.randrange(n), rnd.randint(0, 10**6), 'c%d' % rnd.randrange(6)) for _ in range(50000)]\n"
            "result = [sol.min_cost_route(n, edges, 0, n - 1, 10**6), sol.min_cost_route(n, edges, 5, 77, 3)]"), timeout_s=20))
        out.append(case("stress_path_many_colors", (
            "import random\nrnd = random.Random(8)\nn = 10000\n"
            "edges = [(i, i + 1, rnd.randint(1, 10), 'c%d' % rnd.randrange(3)) for i in range(n - 1)]\n"
            "edges += [(rnd.randrange(n), rnd.randrange(n), rnd.randint(1, 1000), 'c%d' % rnd.randrange(3)) for _ in range(40000)]\n"
            "result = sol.min_cost_route(n, edges, 0, n - 1, 7)"), timeout_s=20))
        return out


# ---------------------------------------------------------------- circular picks
@register("exactly-k-non-adjacent-picks-on-a-circle")
class CircularPicks:
    note = "enumerate all k-subsets, check circular non-adjacency"

    def brute(values, k):
        n = len(values)
        if k == 0:
            return 0
        best = None
        for comb in itertools.combinations(range(n), k):
            ok = True
            if n >= 2:
                cs = set(comb)
                for i in comb:
                    if (i + 1) % n in cs and (i + 1) % n != i:
                        ok = False
                        break
            if ok:
                s = sum(values[i] for i in comb)
                best = s if best is None or s > best else best
        if best is None:
            raise ValueError("impossible")
        return best

    def gen(rng):
        n = rng.randint(1, 11)
        lo = rng.choice([-10, -1000000, 0])
        values = [rng.randint(lo, rng.choice([10, 1000000])) for _ in range(n)]
        return (values, rng.randint(0, n))

    def cases(rng):
        f = "best_circular_selection"
        out = [
            call_case("k_zero_all_negative", f, [-5, -6, -7], 0),
            call_case("two_elements_k1_negative", f, [-3, -9], 1),
            call_case("three_k2_raises", f, [1, 2, 3], 2),
            call_case("four_k2_must_alternate", f, [1, 100, 1, 100], 2),
            call_case("five_k2_negatives_forced", f, [-1, -1, -1, -1, -1], 2),
            call_case("five_k3_raises", f, [9, 9, 9, 9, 9], 3),
            call_case("six_k3_alternating", f, [5, 1, 5, 1, 5, 1], 3),
            call_case("k_equals_n_raises", f, [1, 2, 3, 4, 5, 6], 6),
            call_case("single_negative_k1", f, [-10**6], 1),
            call_case("wrap_pair_best", f, [10, 0, 0, 0, 10], 2),
            call_case("extreme_values", f, [10**6, -10**6, 10**6, -10**6, 10**6, -10**6, 10**6], 3),
            call_case("must_take_negative_for_exact_k", f, [100, -50, 100, -50, 100, -50], 3),
        ]
        for k in range(10):
            batch = [CircularPicks.gen(rng) for _ in range(10)]
            # keep raising inputs out of the batch: one failing call would hide the others
            batch = [b for b in batch if CircularPicks._feasible(*b)]
            out.append(batch_case("random_batch_%02d" % k, f, batch))
        for k in range(3):
            batch = []
            for _ in range(6):
                n = rng.randint(12, 60)
                vals = [rng.randint(-10**6, 10**6) for _ in range(n)]
                batch.append((vals, rng.randint(0, n // 2)))
            out.append(batch_case("random_medium_%02d" % k, f, batch))
        out.append(case("stress_n2000_k1000", (
            "import random\nrnd = random.Random(11)\nv = [rnd.randint(-10**6, 10**6) for _ in range(2000)]\n"
            "result = sol.best_circular_selection(v, 1000)"), timeout_s=30))
        out.append(case("stress_n2000_k1001_raises",
                        "result = sol.best_circular_selection([1] * 2000, 1001)", timeout_s=30))
        out.append(case("stress_n1999_k999_odd", (
            "import random\nrnd = random.Random(12)\nv = [rnd.randint(-10**6, 10**6) for _ in range(1999)]\n"
            "result = sol.best_circular_selection(v, 999)"), timeout_s=30))
        return out

    def _feasible(values, k):
        n = len(values)
        return k == 0 or (n == 1 and k == 1) or (n >= 2 and k <= n // 2)


# ---------------------------------------------------------------- grid teleport
@register("grid-shortest-path-with-one-same-label-teleport")
class GridTeleport:
    note = "Dijkstra over (cell, teleport_used) with explicit teleport edges to every other same-label cell"

    def brute(grid, c):
        import heapq
        R, C = len(grid), len(grid[0])
        if grid[0][0] == -1 or grid[R - 1][C - 1] == -1:
            return -1
        dist = {(0, 0, 0): 0}
        pq = [(0, 0, 0, 0)]
        while pq:
            d, r, col, used = heapq.heappop(pq)
            if d > dist[(r, col, used)]:
                continue
            if (r, col) == (R - 1, C - 1):
                return d
            nxt = []
            for nr, nc in ((r + 1, col), (r - 1, col), (r, col + 1), (r, col - 1)):
                if 0 <= nr < R and 0 <= nc < C and grid[nr][nc] != -1:
                    nxt.append((d + 1, nr, nc, used))
            if not used:
                for rr in range(R):
                    for cc in range(C):
                        if (rr, cc) != (r, col) and grid[rr][cc] == grid[r][col]:
                            nxt.append((d + c, rr, cc, 1))
            for nd, nr, nc, nu in nxt:
                if nd < dist.get((nr, nc, nu), float("inf")):
                    dist[(nr, nc, nu)] = nd
                    heapq.heappush(pq, (nd, nr, nc, nu))
        return -1

    def gen(rng):
        R, C = rng.randint(1, 5), rng.randint(1, 5)
        labels = rng.choice([[0], [0, 1], [0, 1, 2, 3], [7, 10**6]])
        p = rng.choice([0.0, 0.2, 0.4, 0.6])
        grid = [[-1 if rng.random() < p else rng.choice(labels) for _ in range(C)] for _ in range(R)]
        return (grid, rng.choice([0, 1, 2, 3, 5, 20]))

    def cases(rng):
        f = "min_steps"
        out = [
            call_case("start_cell_unique_label_no_teleport", f, [[1, -1], [-1, 2]], 0),
            call_case("teleport_to_self_label_not_target", f, [[4, -1, 4], [-1, -1, 9]], 0),
            call_case("single_row_teleport", f, [[3, -1, -1, 3]], 5),
            call_case("single_column", f, [[1], [2], [-1], [2], [1]], 2),
            call_case("teleport_mid_path", f, [[0, 1, -1, 5], [-1, 2, -1, 2], [-1, -1, -1, 6]], 4),
            call_case("teleport_used_only_once", f, [[1, -1, 1, -1, 2, -1, 2]], 0),
            call_case("label_max_value", f, [[10**6, -1], [-1, 10**6]], 10**6),
            call_case("cost_equal_to_walk", f, [[5, 5, 5, 5]], 3),
            call_case("walk_one_cheaper_than_teleport", f, [[5, 5, 5, 5]], 4),
            call_case("teleport_from_label_reached_by_walk", f, [[0, 1, -1, -1], [-1, 8, -1, 8], [-1, -1, -1, 3]], 1),
            call_case("target_blocked_only", f, [[0, 0], [0, -1]], 0),
        ]
        for k in range(10):
            batch = [GridTeleport.gen(rng) for _ in range(10)]
            out.append(batch_case("random_batch_%02d" % k, f, batch))
        for k in range(3):
            batch = []
            for _ in range(5):
                R, C = rng.randint(6, 20), rng.randint(6, 20)
                labels = list(range(rng.randint(1, 6)))
                p = rng.choice([0.2, 0.35, 0.5])
                grid = [[-1 if rng.random() < p else rng.choice(labels) for _ in range(C)] for _ in range(R)]
                grid[0][0] = 0
                grid[R - 1][C - 1] = rng.choice(labels)
                batch.append((grid, rng.choice([0, 3, 10])))
            out.append(batch_case("random_medium_%02d" % k, f, batch))
        out.append(case("stress_uniform_label_wall_forces_teleport", (
            "R = C = 300\ngrid = [[2] * C for _ in range(R)]\n"
            "for r in range(R):\n    grid[r][150] = -1\n"
            "result = sol.min_steps(grid, 7)"), timeout_s=20))
        out.append(case("stress_serpentine_uniform_label", (
            "R = C = 300\ngrid = [[1] * C for _ in range(R)]\n"
            "for r in range(1, R, 2):\n"
            "    for c in range(C):\n        grid[r][c] = -1\n"
            "    grid[r][C - 1 if r % 4 == 1 else 0] = 1\n"
            "result = [sol.min_steps(grid, 10**6), sol.min_steps(grid, 50)]"), timeout_s=20))
        out.append(case("stress_random_two_labels", (
            "import random\nrnd = random.Random(21)\nR = C = 300\n"
            "grid = [[-1 if rnd.random() < 0.3 else rnd.randrange(2) for _ in range(C)] for _ in range(R)]\n"
            "grid[0][0] = 0\ngrid[R - 1][C - 1] = 1\n"
            "result = sol.min_steps(grid, 25)"), timeout_s=20))
        return out


# ---------------------------------------------------------------- interval scheduling
@register("interval-scheduling-with-mandatory-cooldown-gap")
class MaxSessions:
    note = "enumerate all subsets, check gap constraint after sorting by start"

    def brute(intervals, gap):
        n = len(intervals)
        best = 0
        for mask in range(1 << n):
            sel = sorted(intervals[i] for i in range(n) if mask >> i & 1)
            if len(sel) <= best:
                continue
            if all(sel[i + 1][0] >= sel[i][1] + gap for i in range(len(sel) - 1)):
                best = len(sel)
        return best

    def gen(rng):
        n = rng.randint(0, 10)
        span = rng.choice([5, 15, 40])
        ivs = []
        for _ in range(n):
            s = rng.randint(0, span)
            ivs.append((s, s + rng.randint(1, rng.choice([1, 3, 10]))))
        return (ivs, rng.choice([0, 0, 1, 2, 3, 7]))

    def cases(rng):
        f = "max_sessions"
        out = [
            call_case("empty_gap_zero", f, [], 0),
            call_case("touching_chain_gap_zero", f, [(i, i + 1) for i in range(10)], 0),
            call_case("touching_chain_gap_one", f, [(i, i + 1) for i in range(10)], 1),
            call_case("max_bounds", f, [(0, 10**9), (0, 1), (10**9 - 1, 10**9)], 0),
            call_case("gap_exact_fit_large", f, [(0, 1), (10**9 - 1, 10**9)], 10**9 - 2),
            call_case("gap_one_too_large", f, [(0, 1), (10**9 - 1, 10**9)], 10**9 - 1),
            call_case("same_end_different_start", f, [(0, 5), (4, 5), (3, 5), (5, 6)], 0),
            call_case("short_late_vs_long_early", f, [(0, 3), (2, 4), (4, 5), (6, 8)], 1),
            call_case("all_duplicates_with_gap", f, [(3, 4)] * 7, 0),
            call_case("earliest_start_is_wrong_greedy", f, [(0, 100), (1, 2), (3, 4), (5, 6)], 1),
            call_case("shortest_is_wrong_greedy", f, [(0, 5), (4, 7), (6, 11)], 0),
        ]
        for k in range(12):
            batch = [MaxSessions.gen(rng) for _ in range(10)]
            out.append(batch_case("random_batch_%02d" % k, f, batch))
        out.append(case("stress_nested_100k", (
            "ivs = [(i, 2 * 10**5 - i) for i in range(10**5)]\n"
            "result = [sol.max_sessions(ivs, 0), sol.max_sessions(ivs[::-1], 5)]"), timeout_s=15))
        out.append(case("stress_chain_100k_gap", (
            "ivs = [(3 * i, 3 * i + 2) for i in range(10**5)][::-1]\n"
            "result = [sol.max_sessions(ivs, 1), sol.max_sessions(ivs, 2), sol.max_sessions(ivs, 4)]"), timeout_s=15))
        out.append(case("stress_dense_random_100k", (
            "import random\nrnd = random.Random(31)\nivs = []\n"
            "for _ in range(10**5):\n    s = rnd.randrange(0, 10**6)\n    ivs.append((s, s + rnd.randrange(1, 10**4)))\n"
            "result = sol.max_sessions(ivs, 37)"), timeout_s=15))
        return out


# ---------------------------------------------------------------- balanced brackets
@register("lexicographically-smallest-balanced-bracket-completion")
class SmallestBalanced:
    note = "enumerate every '?' assignment, keep balanced ones, take min"

    def brute(s):
        qs = [i for i, ch in enumerate(s) if ch == "?"]
        best = None
        for bits in itertools.product("()", repeat=len(qs)):
            t = list(s)
            for i, b in zip(qs, bits):
                t[i] = b
            bal = 0
            ok = True
            for ch in t:
                bal += 1 if ch == "(" else -1
                if bal < 0:
                    ok = False
                    break
            if ok and bal == 0:
                cand = "".join(t)
                if best is None or cand < best:
                    best = cand
        if best is None:
            raise ValueError("no completion")
        return best

    def gen(rng):
        n = rng.randint(0, 12)
        w = rng.choice([(1, 1, 1), (1, 1, 4), (3, 1, 2), (1, 3, 2)])
        return ("".join(rng.choices("()?", weights=w, k=n)),)

    def cases(rng):
        f = "smallest_balanced"
        out = [
            call_case("two_marks", f, "??"),
            call_case("close_then_marks_raises", f, ")???"),
            call_case("open_at_end_raises", f, "??(?"),
            call_case("all_fixed_unbalanced_raises", f, "(()("),
            call_case("fixed_balanced_complex", f, "(()())()"),
            call_case("marks_must_be_close_after_opens", f, "((??"),
            call_case("marks_between_fixed", f, "?)(?"),
            call_case("greedy_prefix_check", f, "?))?"),
            call_case("deep_nesting_marks", f, "?" * 20),
            call_case("trailing_close_fixed", f, "???)"),
            call_case("open_needed_late", f, "()??()?)"),
        ]
        for k in range(12):
            batch = []
            while len(batch) < 10:
                (s,) = SmallestBalanced.gen(rng)
                try:
                    SmallestBalanced.brute(s)
                except ValueError:
                    if k % 3 or any(c["name"] == "random_raises_%02d" % k for c in out):
                        continue
                    out.append(call_case("random_raises_%02d" % k, f, s))
                    continue
                batch.append((s,))
            out.append(batch_case("random_batch_%02d" % k, f, batch))
        out.append(case("stress_all_marks_100k", "result = sol.smallest_balanced('?' * 100000)", timeout_s=10))
        out.append(case("stress_half_open_fixed", "result = sol.smallest_balanced('(' * 50000 + '?' * 50000)", timeout_s=10))
        out.append(case("stress_random_valid_masked", (
            "import random\nrnd = random.Random(41)\nbal = 0\nt = []\n"
            "for i in range(100000):\n    rem = 100000 - i\n"
            "    if bal == 0 or (bal < rem and rnd.random() < 0.5):\n        t.append('('); bal += 1\n"
            "    else:\n        t.append(')'); bal -= 1\n"
            "s = ''.join(c if rnd.random() < 0.6 else '?' for c in t)\n"
            "result = sol.smallest_balanced(s)"), timeout_s=10))
        out.append(case("stress_impossible_raises", "result = sol.smallest_balanced('(' * 50001 + '?' * 49999)", timeout_s=10))
        return out


# ---------------------------------------------------------------- spaced repeat
@register("longest-repeated-substring-with-enforced-spacing")
class SpacedRepeat:
    note = "for every L, p, q with q >= p + L + gap compare slices directly"

    def brute(s, gap):
        n = len(s)
        for L in range(n, 0, -1):
            for p in range(n):
                for q in range(p + L + gap, n - L + 1):
                    if s[p:p + L] == s[q:q + L]:
                        return L
        return 0

    def gen(rng):
        n = rng.randint(0, 14)
        alpha = rng.choice(["a", "ab", "abc", "a b~"])
        s = "".join(rng.choice(alpha) for _ in range(n))
        return (s, rng.randint(0, n))

    def cases(rng):
        f = "longest_spaced_repeat"
        out = [
            call_case("empty_gap_zero", f, "", 0),
            call_case("two_same_gap_zero", f, "aa", 0),
            call_case("two_same_gap_one", f, "aa", 1),
            call_case("aba_gap_one", f, "aba", 1),
            call_case("aaaaa_gap_zero", f, "aaaaa", 0),
            call_case("aaaaaa_gap_zero", f, "aaaaaa", 0),
            call_case("aaaaaa_gap_two", f, "aaaaaa", 2),
            call_case("gap_equals_len", f, "abab", 4),
            call_case("punctuation_and_spaces", f, "a b!a b!", 0),
            call_case("case_sensitive", f, "abcABC", 0),
            call_case("later_pair_longer", f, "xyzxyz--abcdabcd", 0),
            call_case("gap_trims_overlong_match", f, "abcdefgabcdefg", 3),
        ]
        for k in range(12):
            batch = [SpacedRepeat.gen(rng) for _ in range(12)]
            out.append(batch_case("random_batch_%02d" % k, f, batch))
        out.append(case("stress_all_same_1000", (
            "s = 'a' * 1000\nresult = [sol.longest_spaced_repeat(s, g) for g in (0, 1, 333, 998, 1000)]"), timeout_s=20))
        out.append(case("stress_printable_random_1000", (
            "import random\nrnd = random.Random(51)\n"
            "s = ''.join(chr(rnd.randint(32, 126)) for _ in range(1000))\n"
            "result = [sol.longest_spaced_repeat(s, 0), sol.longest_spaced_repeat(s, 10)]"), timeout_s=20))
        out.append(case("stress_planted_repeat_1000", (
            "import random\nrnd = random.Random(52)\n"
            "block = ''.join(rnd.choice('ab') for _ in range(300))\n"
            "s = block + ''.join(rnd.choice('ab') for _ in range(400)) + block\n"
            "result = [sol.longest_spaced_repeat(s, 0), sol.longest_spaced_repeat(s, 400), sol.longest_spaced_repeat(s, 401)]"),
            timeout_s=20))
        return out


# ---------------------------------------------------------------- palindrome insertions
@register("palindrome-insertions-from-a-restricted-alphabet")
class PalindromeInsertions:
    note = "enumerate the set U of unmatched chars (each needs one inserted copy, so U must be allowed); s minus U must be a palindrome"

    def brute(s, allowed):
        allowed = set(allowed)
        n = len(s)
        best = None
        for mask in range(1 << n):
            cnt = bin(mask).count("1")
            if best is not None and cnt >= best:
                continue
            if any(mask >> i & 1 and s[i] not in allowed for i in range(n)):
                continue
            rest = [s[i] for i in range(n) if not mask >> i & 1]
            if rest == rest[::-1]:
                best = cnt
        return -1 if best is None else best

    def gen(rng):
        n = rng.randint(0, 11)
        s = "".join(rng.choice(rng.choice(["ab", "abc", "a b"])) for _ in range(n))
        allowed = "".join(sorted(set(rng.sample("abcd ", rng.randint(0, 5)))))
        kind = rng.randrange(3)
        allowed = allowed if kind == 0 else (list(allowed) if kind == 1 else set(allowed))
        return (s, allowed)

    def cases(rng):
        f = "min_insertions"
        out = [
            call_case("two_equal_no_alphabet", f, "aa", ""),
            call_case("two_diff_one_allowed", f, "ab", "b"),
            call_case("two_diff_other_allowed", f, "ab", "a"),
            call_case("allowed_unrelated_chars", f, "ab", "xyz"),
            call_case("allowed_tuple", f, "abcb", ("a", "b")),
            call_case("allowed_frozenset", f, "race", frozenset("acer")),
            case("allowed_generator", "result = sol.min_insertions('abcb', (c for c in 'ab'))"),
            case("allowed_dict_keys", "result = sol.min_insertions('race', {'a': 1, 'c': 2, 'e': 3, 'r': 4}.keys())"),
            call_case("allowed_with_duplicates", f, "abc", "aaabbbccc"),
            call_case("center_char_not_allowed", f, "aba", ""),
            call_case("only_char_not_allowed_inside", f, "abca", "b"),
            call_case("only_char_not_allowed_inside_c", f, "abca", "c"),
            call_case("punctuation_alphabet", f, "!?", "!"),
            call_case("space_char", f, "a ", " "),
            call_case("case_sensitive", f, "Aa", "a"),
        ]
        for k in range(12):
            batch = [PalindromeInsertions.gen(rng) for _ in range(10)]
            out.append(batch_case("random_batch_%02d" % k, f, batch))
        out.append(case("stress_300_full_alphabet", (
            "import random\nrnd = random.Random(61)\n"
            "s = ''.join(chr(rnd.randint(33, 126)) for _ in range(300))\n"
            "result = [sol.min_insertions(s, [chr(i) for i in range(32, 127)]), sol.min_insertions(s, s[:150])]"),
            timeout_s=20))
        out.append(case("stress_300_restricted", (
            "import random\nrnd = random.Random(62)\n"
            "s = ''.join(rnd.choice('abcd') for _ in range(300))\n"
            "result = [sol.min_insertions(s, 'abc'), sol.min_insertions(s, 'abcd'), sol.min_insertions(s, '')]"),
            timeout_s=20))
        return out


# ---------------------------------------------------------------- congruences
@register("smallest-solution-of-congruences-with-non-coprime-moduli")
class Congruences:
    note = "scan x = 0 .. lcm-1 checking every congruence"

    def brute(pairs):
        L = 1
        for _, m in pairs:
            L = L * m // math.gcd(L, m)
        for x in range(L):
            if all(x % m == r % m for r, m in pairs):
                return x
        raise ValueError("none")

    def gen(rng):
        k = rng.randint(0, 4)
        mods = [rng.choice([1, 2, 3, 4, 6, 8, 9, 10, 12, 15, 18, 20, 25, 30]) for _ in range(k)]
        if rng.random() < 0.5:
            x = rng.randint(0, 5000)
            return ([(x % m + m * rng.randint(-3, 3), m) for m in mods],)
        return ([(rng.randint(-60, 60), m) for m in mods],)

    def cases(rng):
        f = "solve_congruences"
        out = [
            call_case("single_pair", f, [(4, 7)]),
            call_case("single_negative_residue", f, [(-1, 10**9)]),
            call_case("residue_equal_modulus", f, [(6, 6), (0, 4)]),
            call_case("duplicate_pairs", f, [(3, 8), (3, 8), (3, 8)]),
            call_case("same_modulus_conflict_raises", f, [(3, 8), (4, 8)]),
            call_case("same_modulus_equivalent_residues", f, [(3, 8), (11, 8), (-5, 8)]),
            call_case("divisor_modulus_consistent", f, [(7, 12), (1, 3), (3, 4)]),
            call_case("divisor_modulus_inconsistent", f, [(7, 12), (2, 3)]),
            call_case("large_prime_moduli", f, [(123456, 999999937), (654321, 999999929), (1, 2)]),
            call_case("large_shared_factor", f, [(10**9 - 1, 10**9), (5 * 10**8 - 1, 5 * 10**8)]),
            call_case("large_shared_factor_inconsistent", f, [(10**9 - 1, 10**9), (0, 5 * 10**8)]),
            call_case("huge_residue_values", f, [(10**18 + 7, 97), (-(10**18), 89)]),
            call_case("all_moduli_one", f, [(5, 1), (-7, 1), (0, 1)]),
            call_case("answer_is_lcm_minus_one", f, [(-1, 4), (-1, 6), (-1, 9), (-1, 10)]),
            call_case("inconsistent_last_of_twenty", f, [(0, 2)] * 19 + [(1, 4)]),
        ]
        for k in range(12):
            batch = []
            while len(batch) < 10:
                args = Congruences.gen(rng)
                try:
                    Congruences.brute(*args)
                except ValueError:
                    if k % 2 or any(c["name"] == "random_raises_%02d" % k for c in out):
                        continue
                    out.append(call_case("random_raises_%02d" % k, f, *args))
                    continue
                batch.append(args)
            out.append(batch_case("random_batch_%02d" % k, f, batch))
        out.append(case("twenty_pairwise_coprime_primes", (
            "ps = [999999937, 999999929, 999999893, 999999883, 999999797, 999999761, 999999757, 999999751,\n"
            "      999999739, 999999733, 999999677, 999999667, 999999613, 999999607, 999999599, 999999587,\n"
            "      999999541, 999999527, 999999503, 999999491]\n"
            "x0 = 3 ** 170 + 12345\nL = 1\nfor p in ps:\n    L *= p\n"
            "result = (sol.solve_congruences([(x0 % p - p, p) for p in ps]) == x0 % L, sol.solve_congruences([(x0 % p, p) for p in ps]))"),
            timeout_s=10))
        out.append(case("twenty_non_coprime_large", (
            "import random\nrnd = random.Random(71)\nx0 = rnd.randrange(10**60)\n"
            "mods = [rnd.randrange(1, 10**5) * rnd.choice([2, 6, 30, 210, 2310]) for _ in range(20)]\n"
            "result = sol.solve_congruences([(x0 % m + m * rnd.randint(-5, 5), m) for m in mods])"), timeout_s=10))
        return out
