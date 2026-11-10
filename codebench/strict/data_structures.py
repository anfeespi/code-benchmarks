"""v4-strict specs: data_structures.

Every problem is a stateful class, so a case is an op script replayed against sol.<Class>.
The trace records each op's return value (deep-copied at call time) or, for a raised exception,
"!<Name>" where <Name> is the prompt-named exception class it is an instance of. Methods the
prompt declares as returning None are recorded as None (their return value is not tested).
"""
import random

from . import register, case, lit

REPLAY_SRC = r'''
import copy as _copy
def _replay(cls, ctor, ops, noret=()):
    _named = (ValueError, KeyError, IndexError, RuntimeError)
    def _exc(e):
        for c in _named:
            if isinstance(e, c):
                return "!" + c.__name__
        return "!" + type(e).__name__
    try:
        o = cls(*ctor)
    except Exception as e:
        return [_exc(e)]
    out = []
    for m, a in ops:
        try:
            v = len(o) if m == "len" else getattr(o, m)(*a)
            out.append(None if m in noret else _copy.deepcopy(v))
        except Exception as e:
            out.append(_exc(e))
    return out
'''
_ns = {}
exec(REPLAY_SRC, _ns)
_replay = _ns["_replay"]


def script_case(name, cls, ctor, ops, noret, timeout_s=5):
    code = REPLAY_SRC + "result = _replay(sol.%s, %s, %s, %s)" % (cls, lit(tuple(ctor)), lit(ops), lit(tuple(noret)))
    return case(name, code, timeout_s)


def make_call(noret):
    def call(cls, args):
        ctor, ops = args
        return _replay(cls, ctor, ops, noret)
    return call


# ---------------------------------------------------------------------------------------------
# CountingBag
# ---------------------------------------------------------------------------------------------
class RefBag:
    """Naive: list of present items in entry order + counts."""

    def __init__(self):
        self.order = []   # present items, in entry order
        self.cnt = {}

    def add(self, x):
        if self.cnt.get(x, 0) == 0:
            self.order.append(x)
            self.cnt[x] = 0
        self.cnt[x] += 1
        return self.cnt[x]

    def discard(self, x):
        if self.cnt.get(x, 0) == 0:
            return False
        self.cnt[x] -= 1
        if self.cnt[x] == 0:
            del self.cnt[x]
            self.order = [y for y in self.order if not (y == x)]
        return True

    def count(self, x):
        return self.cnt.get(x, 0)

    def __len__(self):
        return sum(self.cnt.values())

    def distinct(self):
        return len(self.order)

    def most_common(self, k):
        if k < 0:
            raise ValueError("k")
        res = []
        for c in sorted(set(self.cnt.values()), reverse=True):
            res += [(x, c) for x in self.order if self.cnt[x] == c]
        return res[:k]


BAG_ITEMS = ["a", "b", "c", "d", "e", 7, 8, (1, 2), None, "é"]


def bag_ops(rng, n, items):
    ops = []
    for _ in range(n):
        r = rng.random()
        x = rng.choice(items)
        if r < 0.45:
            ops.append(("add", (x,)))
        elif r < 0.7:
            ops.append(("discard", (x,)))
        elif r < 0.78:
            ops.append(("count", (x,)))
        elif r < 0.84:
            ops.append(("len", ()))
        elif r < 0.9:
            ops.append(("distinct", ()))
        else:
            ops.append(("most_common", (rng.choice([-1, 0, 1, 2, 3, 5, 20]),)))
    return ops


@register("counting-bag-with-deterministic-most-common-ordering")
class Bag:
    note = "naive reference: entry-ordered list of present items, most_common by count groups"
    n_cross = 600
    call = staticmethod(make_call(()))
    brute = RefBag

    def gen(rng):
        return ((), bag_ops(rng, rng.randint(1, 40), rng.sample(BAG_ITEMS, rng.randint(1, len(BAG_ITEMS)))))

    def cases(rng):
        S = lambda name, ops: script_case(name, "CountingBag", (), ops, ())
        out = [
            S("empty_queries", [("len", ()), ("distinct", ()), ("count", ("x",)), ("discard", ("x",)),
                                ("most_common", (0,)), ("most_common", (1,)), ("most_common", (-1,)), ("len", ())]),
            S("single_item_lifecycle", [("add", ("x",)), ("most_common", (1,)), ("discard", ("x",)),
                                        ("most_common", (1,)), ("distinct", ()), ("len", ()), ("discard", ("x",)),
                                        ("count", ("x",))]),
            S("negative_k_after_items", [("add", (1,)), ("add", (2,)), ("most_common", (-5,)), ("most_common", (2,))]),
            S("count_increments_returned", [("add", ("q",))] * 6 + [("count", ("q",)), ("len", ())]),
            S("reentry_goes_last_among_ties", [("add", ("a",)), ("add", ("b",)), ("add", ("c",)),
                                               ("discard", ("a",)), ("add", ("a",)), ("most_common", (3,)),
                                               ("discard", ("b",)), ("add", ("b",)), ("most_common", (3,))]),
            S("partial_discard_keeps_entry_moment", [("add", ("a",)), ("add", ("a",)), ("add", ("b",)), ("add", ("b",)),
                                                     ("discard", ("a",)), ("add", ("a",)), ("most_common", (2,))]),
            S("count_beats_entry", [("add", ("old",)), ("add", ("new",)), ("add", ("new",)), ("most_common", (1,)),
                                    ("most_common", (2,))]),
            S("falsy_and_unicode_items", [("add", (0,)), ("add", ("",)), ("add", (None,)), ("add", ("ü",)), ("add", ("",)),
                                          ("most_common", (10,)), ("distinct", ()), ("len", ()), ("count", ("",)),
                                          ("discard", (0,)), ("distinct", ()), ("most_common", (10,))]),
            S("tuple_items", [("add", ((1, 2),)), ("add", ((2, 1),)), ("add", ((1, 2),)), ("count", ((1, 2),)),
                              ("most_common", (5,))]),
            S("many_ties_entry_order", [("add", ("i%d" % i,)) for i in range(15)] + [("most_common", (15,)),
                                                                                      ("most_common", (4,))]),
            S("drain_then_refill", [("add", ("a",)), ("add", ("b",)), ("discard", ("a",)), ("discard", ("b",)),
                                    ("len", ()), ("distinct", ()), ("most_common", (5,)), ("add", ("b",)),
                                    ("add", ("a",)), ("most_common", (5,))]),
        ]
        for k in range(22):
            items = rng.sample(BAG_ITEMS, rng.randint(2, len(BAG_ITEMS)))
            ops = bag_ops(rng, rng.randint(30, 120), items) + [("most_common", (len(items),)), ("len", ()),
                                                               ("distinct", ())]
            out.append(S("random_script_%02d" % k, ops))
        return out


# ---------------------------------------------------------------------------------------------
# TTLCache
# ---------------------------------------------------------------------------------------------
class RefTTL:
    """Naive: list of [key, value, stored_at, ttl], index 0 = least recently used."""

    def __init__(self, capacity):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("capacity")
        self.cap = capacity
        self.rows = []
        self.st = {"hits": 0, "misses": 0, "evictions": 0, "expirations": 0}

    def _purge(self, now):
        keep = []
        for r in self.rows:
            if r[3] is not None and now >= r[2] + r[3]:
                self.st["expirations"] += 1
            else:
                keep.append(r)
        self.rows = keep

    def _find(self, key):
        for i, r in enumerate(self.rows):
            if r[0] == key:
                return i
        return -1

    def put(self, key, value, now, ttl=None):
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl")
        self._purge(now)
        i = self._find(key)
        if i >= 0:
            self.rows.pop(i)
        elif len(self.rows) == self.cap:
            self.rows.pop(0)
            self.st["evictions"] += 1
        self.rows.append([key, value, now, ttl])

    def get(self, key, now):
        self._purge(now)
        i = self._find(key)
        if i < 0:
            self.st["misses"] += 1
            return None
        r = self.rows.pop(i)
        self.rows.append(r)
        self.st["hits"] += 1
        return r[1]

    def stats(self):
        return dict(self.st)

    def __len__(self):
        return len(self.rows)


def ttl_ops(rng, n, nkeys, float_time=False):
    ops, now = [], 0
    for i in range(n):
        step = rng.choice([0, 0, 1, 1, 2, 3]) if not float_time else rng.choice([0, 0.25, 0.5, 1, 1.75])
        now += step
        k = "k%d" % rng.randrange(nkeys)
        r = rng.random()
        if r < 0.45:
            ttl = rng.choice([None, None, 1, 2, 3, 5, 8] + ([0.5, 1.25, 2.75] if float_time else []))
            if rng.random() < 0.04:
                ttl = rng.choice([0, -1, -0.5])
            ops.append(("put", (k, i, now, ttl)))
        elif r < 0.85:
            ops.append(("get", (k, now)))
        elif r < 0.93:
            ops.append(("stats", ()))
        else:
            ops.append(("len", ()))
    return ops


@register("lru-cache-with-ttl-and-stats")
class TTL:
    note = "naive reference: recency-ordered list of rows, full purge scan, linear key search"
    n_cross = 600
    call = staticmethod(make_call(("put",)))
    brute = RefTTL

    def gen(rng):
        cap = rng.randint(1, 5)
        return ((cap,), ttl_ops(rng, rng.randint(1, 50), rng.randint(1, 8), rng.random() < 0.3))

    def cases(rng):
        S = lambda name, cap, ops: script_case(name, "TTLCache", (cap,), ops, ("put",))
        out = [
            S("bad_capacity_fraction", 2.5, []),
            S("bad_capacity_zero", 0, []),
            S("bad_capacity_negative", -1, []),
            S("capacity_one_evicts_each_new_key", 1, [("put", ("a", 1, 0)), ("put", ("b", 2, 1)), ("get", ("a", 2)),
                                                       ("get", ("b", 2)), ("put", ("b", 3, 3)), ("stats", ()),
                                                       ("len", ())]),
            S("empty_cache_get_and_stats", 3, [("stats", ()), ("len", ()), ("get", ("x", 0)), ("stats", ())]),
            S("purge_frees_room_no_eviction", 2, [("put", ("a", 1, 0, 5)), ("put", ("b", 2, 1)),
                                                   ("put", ("c", 3, 5)), ("stats", ()), ("len", ()),
                                                   ("get", ("b", 5)), ("get", ("c", 5))]),
            S("purge_happens_on_put_of_existing_key", 3, [("put", ("a", 1, 0, 2)), ("put", ("b", 1, 0, 2)),
                                                           ("put", ("a", 9, 2, 2)), ("stats", ()), ("len", ()),
                                                           ("get", ("a", 3))]),
            S("bad_ttl_no_purge", 2, [("put", ("a", 1, 0, 1)), ("len", ()), ("put", ("b", 1, 10, 0)),
                                       ("len", ()), ("stats", ()), ("put", ("b", 1, 10, -3)), ("stats", ()),
                                       ("len", ())]),
            S("float_times_dead_exactly_at_deadline", 3, [("put", ("a", 1, 0.5, 1.25)), ("get", ("a", 1.5)),
                                                           ("get", ("a", 1.75)), ("stats", ()), ("len", ())]),
            S("float_ttl_just_before_deadline", 2, [("put", ("a", "v", 1, 0.5)), ("get", ("a", 1.25)),
                                                     ("get", ("a", 1.5)), ("stats", ())]),
            S("eviction_after_purge_picks_lru_of_survivors", 3,
              [("put", ("a", 1, 0)), ("put", ("b", 2, 0, 4)), ("put", ("c", 3, 1)), ("get", ("a", 2)),
               ("put", ("d", 4, 3)), ("get", ("b", 3)), ("get", ("c", 3)), ("put", ("e", 5, 4)), ("stats", ()),
               ("get", ("a", 4)), ("get", ("d", 4)), ("get", ("e", 4)), ("stats", ())]),
            S("miss_does_not_refresh", 2, [("put", ("a", 1, 0)), ("put", ("b", 2, 0)), ("get", ("zz", 1)),
                                           ("put", ("c", 3, 2)), ("get", ("a", 3)), ("get", ("b", 3)),
                                           ("stats", ())]),
            S("update_value_none_ttl_clears_expiry", 2, [("put", ("k", 1, 0, 2)), ("put", ("k", 2, 1)),
                                                          ("get", ("k", 1000)), ("stats", ())]),
            S("update_with_ttl_resets_clock", 2, [("put", ("k", 1, 0)), ("put", ("k", 2, 3, 2)), ("get", ("k", 4)),
                                                   ("get", ("k", 5)), ("stats", ())]),
            S("multiple_expire_in_one_call", 4, [("put", ("a", 1, 0, 1)), ("put", ("b", 1, 0, 2)),
                                                  ("put", ("c", 1, 0, 3)), ("put", ("d", 1, 0)), ("len", ()),
                                                  ("get", ("d", 3)), ("stats", ()), ("len", ())]),
            S("none_and_falsy_values_are_hits", 3, [("put", ("z", 0, 0)), ("put", ("e", "", 0)), ("get", ("z", 1)),
                                                     ("get", ("e", 1)), ("stats", ())]),
            S("same_now_many_ops", 2, [("put", ("a", 1, 7)), ("put", ("b", 2, 7)), ("get", ("a", 7)),
                                        ("put", ("c", 3, 7)), ("get", ("b", 7)), ("get", ("c", 7)), ("stats", ())]),
        ]
        for k in range(20):
            cap = rng.choice([1, 2, 3, 4, 6, 10])
            ops = ttl_ops(rng, rng.randint(40, 150), rng.randint(2, 14), k % 3 == 0) + [("stats", ()), ("len", ())]
            out.append(S("random_script_%02d" % k, cap, ops))
        return out


# ---------------------------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------------------------
class RefBoard:
    """Naive: list of [player, best, achieved_at] rows; every query scans."""

    def __init__(self):
        self.rows = []
        self.t = 0

    def _row(self, p):
        for r in self.rows:
            if r[0] == p:
                return r
        return None

    def submit(self, p, s):
        self.t += 1
        r = self._row(p)
        if r is None:
            self.rows.append([p, s, self.t])
            return True
        if s > r[1]:
            r[1], r[2] = s, self.t
            return True
        return False

    def best(self, p):
        r = self._row(p)
        if r is None:
            raise KeyError(p)
        return r[1]

    def rank(self, p):
        b = self.best(p)
        return 1 + len([r for r in self.rows if r[1] > b])

    def top(self, k):
        if k < 0:
            raise ValueError("k")
        res = []
        remaining = list(self.rows)
        while remaining and len(res) < k:
            m = remaining[0]
            for r in remaining[1:]:
                if r[1] > m[1] or (r[1] == m[1] and r[2] < m[2]):
                    m = r
            remaining.remove(m)
            res.append((m[0], m[1]))
        return res

    def player_count(self):
        return len(self.rows)


def board_ops(rng, n, players, lo, hi):
    ops = []
    for _ in range(n):
        r = rng.random()
        p = rng.choice(players)
        if r < 0.5:
            ops.append(("submit", (p, rng.randint(lo, hi))))
        elif r < 0.62:
            ops.append(("best", (p,)))
        elif r < 0.77:
            ops.append(("rank", (p,)))
        elif r < 0.93:
            ops.append(("top", (rng.choice([-1, 0, 1, 2, 3, 5, 50]),)))
        else:
            ops.append(("player_count", ()))
    return ops


@register("leaderboard-with-competition-ranks-and-stable-ties")
class Board:
    note = "naive reference: row list with achievement stamps, selection-sort top, counting rank"
    n_cross = 600
    call = staticmethod(make_call(()))
    brute = RefBoard

    def gen(rng):
        players = ["p%d" % i for i in range(rng.randint(1, 8))]
        lo = rng.choice([0, -5, -1000])
        return ((), board_ops(rng, rng.randint(1, 50), players, lo, lo + rng.choice([2, 5, 30])))

    def cases(rng):
        S = lambda name, ops: script_case(name, "Leaderboard", (), ops, ())
        out = [
            S("empty_board", [("player_count", ()), ("top", (0,)), ("top", (3,)), ("top", (-1,)), ("best", ("x",)),
                              ("rank", ("x",))]),
            S("single_player_rank_one", [("submit", ("solo", -7)), ("rank", ("solo",)), ("best", ("solo",)),
                                         ("top", (1,)), ("submit", ("solo", -8)), ("submit", ("solo", -7)),
                                         ("submit", ("solo", 0)), ("best", ("solo",))]),
            S("all_tied_rank_one", [("submit", ("p%d" % i, 5)) for i in range(6)] +
              [("rank", ("p%d" % i,)) for i in range(6)] + [("top", (6,))]),
            S("rank_skips_after_ties", [("submit", ("a", 9)), ("submit", ("b", 9)), ("submit", ("c", 9)),
                                        ("submit", ("d", 3)), ("submit", ("e", 1)), ("rank", ("d",)),
                                        ("rank", ("e",)), ("rank", ("a",))]),
            S("improvement_moves_to_back_of_new_tie", [("submit", ("a", 10)), ("submit", ("b", 5)),
                                                        ("submit", ("c", 10)), ("submit", ("b", 10)),
                                                        ("top", (3,)), ("submit", ("a", 10)), ("submit", ("a", 4)),
                                                        ("top", (3,))]),
            S("lower_then_equal_resubmits_unchanged", [("submit", ("x", 50)), ("submit", ("y", 50)),
                                                        ("submit", ("x", 49)), ("submit", ("x", 50)),
                                                        ("top", (2,)), ("player_count", ())]),
            S("player_ids_ints_and_unicode", [("submit", (1, 3)), ("submit", ("ñandú", 3)), ("submit", ((2, 2), 4)),
                                              ("top", (5,)), ("rank", (1,)), ("rank", ("ñandú",)),
                                              ("best", ((2, 2),))]),
            S("large_scores", [("submit", ("a", 10**18)), ("submit", ("b", -10**18)), ("submit", ("c", 10**18)),
                               ("rank", ("b",)), ("rank", ("c",)), ("top", (3,))]),
            S("top_k_exceeds_count", [("submit", ("a", 1)), ("submit", ("b", 2)), ("top", (3,)), ("top", (2,)),
                                      ("top", (1,))]),
            S("submit_return_values", [("submit", ("a", 0)), ("submit", ("a", 0)), ("submit", ("a", -1)),
                                       ("submit", ("a", 1)), ("submit", ("b", -100))]),
        ]
        for k in range(22):
            players = ["p%d" % i for i in range(rng.randint(2, 15))]
            lo = rng.choice([0, -50, 100])
            ops = board_ops(rng, rng.randint(40, 140), players, lo, lo + rng.choice([3, 10, 60]))
            ops += [("top", (len(players),)), ("player_count", ())] + [("rank", (p,)) for p in players]
            out.append(S("random_script_%02d" % k, ops))
        return out


# ---------------------------------------------------------------------------------------------
# MergeLedger
# ---------------------------------------------------------------------------------------------
class RefLedger:
    """Naive: explicit list of member sets; history stores the two united sets."""

    def __init__(self):
        self.comps = []
        self.val = {}
        self.hist = []

    def _comp(self, x):
        if x not in self.val:
            raise KeyError(x)
        for c in self.comps:
            if x in c:
                return c

    def add(self, x, value=0):
        if x in self.val:
            raise ValueError(x)
        self.val[x] = value
        self.comps.append({x})

    def merge(self, a, b):
        ca, cb = self._comp(a), self._comp(b)
        if ca is cb:
            return False
        self.comps = [c for c in self.comps if c is not ca and c is not cb]
        self.comps.append(ca | cb)
        self.hist.append((set(ca), set(cb)))
        return True

    def same(self, a, b):
        return self._comp(a) is self._comp(b)

    def component_size(self, x):
        return len(self._comp(x))

    def component_value(self, x):
        return sum(self.val[e] for e in self._comp(x))

    def add_value(self, x, d):
        if x not in self.val:
            raise KeyError(x)
        self.val[x] += d

    def components(self):
        return len(self.comps)

    def undo(self):
        if not self.hist:
            raise RuntimeError("empty")
        a, b = self.hist.pop()
        u = a | b
        self.comps = [c for c in self.comps if c != u] + [a, b]


def ledger_ops(rng, n, names, unknown=True):
    ops, present = [], []
    for _ in range(n):
        r = rng.random()
        pool = present + (["zz"] if unknown and rng.random() < 0.05 else [])
        if r < 0.2 or not present:
            x = rng.choice(names)
            if rng.random() < 0.2:
                ops.append(("add", (x,)))
            else:
                ops.append(("add", (x, rng.randint(-5, 9))))
            if x not in present:
                present.append(x)
        elif r < 0.45:
            ops.append(("merge", (rng.choice(pool), rng.choice(pool))))
        elif r < 0.58:
            ops.append(("undo", ()))
        elif r < 0.66:
            ops.append(("same", (rng.choice(pool), rng.choice(pool))))
        elif r < 0.74:
            ops.append(("component_size", (rng.choice(pool),)))
        elif r < 0.84:
            ops.append(("component_value", (rng.choice(pool),)))
        elif r < 0.93:
            ops.append(("add_value", (rng.choice(pool), rng.randint(-10, 10))))
        else:
            ops.append(("components", ()))
    return ops


@register("mergeable-component-ledger-with-undo")
class Ledger:
    note = "naive reference: explicit list of member sets, undo splits the union back into the stored pair"
    n_cross = 600
    call = staticmethod(make_call(("add", "add_value", "undo")))
    brute = RefLedger

    def gen(rng):
        names = ["n%d" % i for i in range(rng.randint(1, 8))]
        return ((), ledger_ops(rng, rng.randint(1, 60), names))

    def cases(rng):
        S = lambda name, ops: script_case(name, "MergeLedger", (), ops, ("add", "add_value", "undo"))
        out = [
            S("empty_ledger", [("components", ()), ("undo", ()), ("same", ("a", "b")), ("component_size", ("a",)),
                               ("components", ())]),
            S("default_value_zero", [("add", ("a",)), ("component_value", ("a",)), ("add", ("b",)),
                                     ("merge", ("a", "b")), ("component_value", ("b",))]),
            S("self_merge_not_recorded", [("add", ("a", 1)), ("merge", ("a", "a")), ("undo", ()),
                                          ("components", ())]),
            S("chain_merge_then_full_undo", [("add", (i, 1)) for i in range(6)] +
              [("merge", (i, i + 1)) for i in range(5)] + [("components", ()), ("component_size", (0,))] +
              [x for i in range(5) for x in [("undo", ()), ("components", ()), ("component_size", (0,)),
                                             ("component_size", (5,))]] + [("undo", ())]),
            S("undo_then_remerge_differently", [("add", ("a", 1)), ("add", ("b", 2)), ("add", ("c", 3)),
                                                ("merge", ("a", "b")), ("undo", ()), ("merge", ("b", "c")),
                                                ("same", ("a", "b")), ("same", ("b", "c")), ("undo", ()),
                                                ("same", ("b", "c")), ("undo", ())]),
            S("undo_keeps_late_added_element", [("add", ("a", 1)), ("add", ("b", 1)), ("merge", ("a", "b")),
                                                 ("add", ("c", 5)), ("merge", ("c", "a")), ("component_value", ("b",)),
                                                 ("undo", ()), ("component_value", ("c",)), ("component_value", ("a",)),
                                                 ("undo", ()), ("components", ())]),
            S("small_into_big_and_back", [("add", ("n%d" % i, i)) for i in range(5)] +
              [("merge", ("n0", "n1")), ("merge", ("n2", "n0")), ("merge", ("n3", "n4")), ("merge", ("n3", "n1")),
               ("component_size", ("n4",)), ("component_value", ("n4",)), ("undo", ()),
               ("same", ("n4", "n0")), ("same", ("n2", "n1")), ("component_value", ("n0",)),
               ("component_value", ("n3",)), ("undo", ()), ("component_size", ("n2",)), ("component_size", ("n0",))]),
            S("noop_merges_between_undos", [("add", ("a",)), ("add", ("b",)), ("add", ("c",)), ("merge", ("a", "b")),
                                            ("merge", ("b", "a")), ("merge", ("a", "c")), ("merge", ("c", "b")),
                                            ("undo", ()), ("merge", ("b", "a")), ("undo", ()), ("same", ("a", "b")),
                                            ("undo", ())]),
            S("duplicate_add_after_merge", [("add", ("a", 1)), ("add", ("b", 2)), ("merge", ("a", "b")),
                                            ("add", ("b", 99)), ("component_value", ("a",)), ("undo", ()),
                                            ("component_value", ("b",))]),
            S("unknown_element_errors", [("add", ("a", 1)), ("merge", ("a", "q")), ("merge", ("q", "a")),
                                         ("same", ("q", "a")), ("same", ("a", "q")), ("component_size", ("q",)),
                                         ("component_value", ("q",)), ("add_value", ("q", 1)), ("components", ()),
                                         ("undo", ())]),
            S("mixed_label_types", [("add", (0, 1)), ("add", ("0", 2)), ("add", ((0,), 3)), ("add", (None, 4)),
                                    ("merge", (0, None)), ("merge", ("0", (0,))), ("same", (0, "0")),
                                    ("component_value", (None,)), ("component_value", ((0,),)), ("undo", ()),
                                    ("component_value", ("0",))]),
            S("negative_values", [("add", ("a", -5)), ("add", ("b", 5)), ("merge", ("a", "b")),
                                  ("component_value", ("a",)), ("add_value", ("a", -10)), ("component_value", ("b",)),
                                  ("undo", ()), ("component_value", ("a",)), ("component_value", ("b",))]),
        ]
        for k in range(20):
            names = ["n%d" % i for i in range(rng.randint(3, 14))]
            ops = ledger_ops(rng, rng.randint(40, 150), names) + [("components", ())]
            out.append(S("random_script_%02d" % k, ops))
        return out


# ---------------------------------------------------------------------------------------------
# IntervalSet
# ---------------------------------------------------------------------------------------------
class RefIntervals:
    """Naive: explicit Python set of covered integers."""

    def __init__(self):
        self.s = set()

    @staticmethod
    def _chk(lo, hi):
        if lo >= hi:
            raise ValueError("bounds")

    @staticmethod
    def _runs(points):
        out = []
        for x in sorted(points):
            if out and out[-1][1] == x:
                out[-1][1] = x + 1
            else:
                out.append([x, x + 1])
        return [tuple(r) for r in out]

    def add(self, lo, hi):
        self._chk(lo, hi)
        self.s.update(range(lo, hi))

    def remove(self, lo, hi):
        self._chk(lo, hi)
        self.s.difference_update(range(lo, hi))

    def contains(self, x):
        return x in self.s

    def total(self):
        return len(self.s)

    def intervals(self):
        return self._runs(self.s)

    def gaps(self, lo, hi):
        self._chk(lo, hi)
        return self._runs(x for x in range(lo, hi) if x not in self.s)


def iv_ops(rng, n, lo, hi):
    ops = []
    for _ in range(n):
        r = rng.random()
        a = rng.randint(lo, hi)
        b = a + rng.choice([1, 1, 2, 3, 5, 10, 25]) if rng.random() > 0.06 else a - rng.randint(0, 3)
        if r < 0.35:
            ops.append(("add", (a, b)))
        elif r < 0.55:
            ops.append(("remove", (a, b)))
        elif r < 0.67:
            ops.append(("contains", (rng.randint(lo - 2, hi + 2),)))
        elif r < 0.75:
            ops.append(("total", ()))
        elif r < 0.88:
            ops.append(("intervals", ()))
        else:
            ops.append(("gaps", (a, b)))
    return ops


@register("normalized-integer-interval-set")
class Intervals:
    note = "naive reference: explicit set of covered integers, runs recomputed on demand"
    n_cross = 600
    call = staticmethod(make_call(("add", "remove")))
    brute = RefIntervals

    def gen(rng):
        lo = rng.choice([-20, 0, 5])
        return ((), iv_ops(rng, rng.randint(1, 40), lo, lo + rng.choice([10, 30, 60])))

    def cases(rng):
        S = lambda name, ops: script_case(name, "IntervalSet", (), ops, ("add", "remove"))
        out = [
            S("empty_set_queries", [("intervals", ()), ("total", ()), ("contains", (0,)), ("gaps", (-3, 3)),
                                    ("remove", (0, 10)), ("intervals", ()), ("total", ())]),
            S("single_point", [("add", (5, 6)), ("intervals", ()), ("contains", (5,)), ("contains", (6,)),
                               ("contains", (4,)), ("total", ()), ("gaps", (4, 7)), ("remove", (5, 6)),
                               ("intervals", ())]),
            S("touch_on_left_and_right", [("add", (10, 20)), ("add", (5, 10)), ("intervals", ()), ("add", (20, 21)),
                                          ("intervals", ()), ("add", (22, 23)), ("intervals", ()),
                                          ("add", (21, 22)), ("intervals", ())]),
            S("add_contained_noop", [("add", (0, 100)), ("add", (10, 20)), ("add", (0, 100)), ("add", (99, 100)),
                                     ("intervals", ()), ("total", ())]),
            S("add_bridges_many", [("add", (i * 3, i * 3 + 1)) for i in range(8)] +
              [("intervals", ()), ("add", (1, 21)), ("intervals", ()), ("total", ())]),
            S("remove_exact_interval", [("add", (0, 5)), ("add", (10, 15)), ("remove", (10, 15)),
                                        ("intervals", ()), ("remove", (0, 5)), ("intervals", ()), ("total", ())]),
            S("remove_touching_edges_noop", [("add", (5, 10)), ("remove", (0, 5)), ("remove", (10, 20)),
                                             ("intervals", ()), ("total", ())]),
            S("remove_spanning_several", [("add", (0, 3)), ("add", (5, 8)), ("add", (10, 13)), ("remove", (2, 11)),
                                          ("intervals", ()), ("total", ())]),
            S("remove_left_and_right_trim", [("add", (0, 10)), ("remove", (-5, 1)), ("remove", (9, 15)),
                                             ("intervals", ()), ("contains", (0,)), ("contains", (1,)),
                                             ("contains", (8,)), ("contains", (9,))]),
            S("negative_coordinates", [("add", (-10, -5)), ("add", (-5, -1)), ("remove", (-7, -6)),
                                       ("intervals", ()), ("gaps", (-12, 0)), ("total", ())]),
            S("huge_coordinates", [("add", (-10**18, 10**18)), ("total", ()), ("remove", (0, 1)),
                                   ("intervals", ()), ("contains", (10**18 - 1,)), ("contains", (10**18,)),
                                   ("gaps", (-10**18 - 5, -10**18 + 1)), ("total", ())]),
            S("gaps_window_fully_covered", [("add", (0, 10)), ("gaps", (0, 10)), ("gaps", (3, 4)), ("gaps", (9, 10))]),
            S("gaps_window_inside_hole", [("add", (0, 2)), ("add", (8, 10)), ("gaps", (3, 5)), ("gaps", (2, 8)),
                                          ("gaps", (1, 9)), ("gaps", (-1, 11))]),
            S("gaps_single_unit_windows", [("add", (0, 1)), ("add", (2, 3))] +
              [("gaps", (x, x + 1)) for x in range(-1, 4)]),
            S("invalid_bounds_each_method", [("add", (0, 5)), ("add", (3, 3)), ("add", (4, 2)), ("remove", (2, 2)),
                                             ("remove", (5, 1)), ("gaps", (1, 1)), ("gaps", (9, 0)),
                                             ("intervals", ()), ("total", ())]),
            S("contains_boundaries", [("add", (-3, 3))] + [("contains", (x,)) for x in range(-5, 6)]),
        ]
        for k in range(20):
            lo = rng.choice([-40, -10, 0, 1000])
            ops = iv_ops(rng, rng.randint(30, 120), lo, lo + rng.choice([20, 50, 120]))
            ops += [("intervals", ()), ("total", ()), ("gaps", (lo - 5, lo + 130))]
            out.append(S("random_script_%02d" % k, ops))
        return out


# ---------------------------------------------------------------------------------------------
# TaskScheduler
# ---------------------------------------------------------------------------------------------
class RefSched:
    """Naive: dict task -> [priority, submission_seq]; pop/peek scan everything."""

    def __init__(self):
        self.t = {}
        self.seq = 0

    def submit(self, tid, p):
        if tid in self.t:
            raise ValueError(tid)
        self.seq += 1
        self.t[tid] = [p, self.seq]

    def reprioritize(self, tid, p):
        if tid not in self.t:
            raise KeyError(tid)
        self.t[tid][0] = p

    def cancel(self, tid):
        if tid not in self.t:
            raise KeyError(tid)
        del self.t[tid]

    def peek(self):
        if not self.t:
            raise IndexError("empty")
        best = None
        for k, (p, s) in self.t.items():
            if best is None or p > self.t[best][0] or (p == self.t[best][0] and s < self.t[best][1]):
                best = k
        return best

    def pop(self):
        k = self.peek()
        del self.t[k]
        return k

    def priority_of(self, tid):
        if tid not in self.t:
            raise KeyError(tid)
        return self.t[tid][0]

    def __len__(self):
        return len(self.t)


def sched_ops(rng, n, ids, plo, phi):
    ops = []
    for _ in range(n):
        r = rng.random()
        t = rng.choice(ids)
        p = rng.randint(plo, phi)
        if r < 0.3:
            ops.append(("submit", (t, p)))
        elif r < 0.45:
            ops.append(("reprioritize", (t, p)))
        elif r < 0.53:
            ops.append(("cancel", (t,)))
        elif r < 0.7:
            ops.append(("pop", ()))
        elif r < 0.8:
            ops.append(("peek", ()))
        elif r < 0.9:
            ops.append(("priority_of", (t,)))
        else:
            ops.append(("len", ()))
    return ops


STRESS_SCHED = r'''
import random
rnd = random.Random(%d)
ts = sol.TaskScheduler()
N = %d
for i in range(N):
    ts.submit(i, rnd.randrange(%d))
acc = 0
for i in range(%d):
    r = rnd.random()
    t = rnd.randrange(N)
    if r < 0.3:
        try:
            ts.reprioritize(t, rnd.randrange(%d))
        except KeyError:
            acc += 1
    elif r < 0.6:
        acc = (acc * 31 + ts.peek()) %% 1000000007
    else:
        acc = (acc * 31 + ts.pop()) %% 1000000007
result = [acc, len(ts)]
'''


@register("reprioritizable-task-scheduler-with-fifo-ties")
class Sched:
    note = "naive reference: dict of (priority, submission seq), linear scan per peek/pop"
    n_cross = 600
    call = staticmethod(make_call(("submit", "reprioritize", "cancel")))
    brute = RefSched

    def gen(rng):
        ids = ["t%d" % i for i in range(rng.randint(1, 8))]
        lo = rng.choice([-3, 0, 100])
        return ((), sched_ops(rng, rng.randint(1, 50), ids, lo, lo + rng.choice([0, 2, 10])))

    def cases(rng):
        S = lambda name, ops: script_case(name, "TaskScheduler", (), ops, ("submit", "reprioritize", "cancel"))
        out = [
            S("empty_scheduler", [("len", ()), ("pop", ()), ("peek", ()), ("cancel", ("a",)),
                                  ("reprioritize", ("a", 1)), ("priority_of", ("a",)), ("len", ())]),
            S("single_task_cycle", [("submit", ("a", 0)), ("peek", ()), ("len", ()), ("pop", ()), ("len", ()),
                                    ("peek", ()), ("submit", ("a", 0)), ("priority_of", ("a",))]),
            S("duplicate_submit_keeps_original", [("submit", ("a", 1)), ("submit", ("b", 2)), ("submit", ("a", 9)),
                                                  ("priority_of", ("a",)), ("len", ()), ("pop", ()), ("pop", ())]),
            S("promote_then_demote_restores_fifo", [("submit", ("a", 1)), ("submit", ("b", 1)), ("submit", ("c", 1)),
                                                    ("reprioritize", ("c", 9)), ("reprioritize", ("c", 1)),
                                                    ("pop", ()), ("pop", ()), ("pop", ())]),
            S("demote_old_high_does_not_linger", [("submit", ("a", 100)), ("submit", ("b", 50)),
                                                   ("reprioritize", ("a", 1)), ("reprioritize", ("a", 100)),
                                                   ("reprioritize", ("a", 2)), ("peek", ()), ("pop", ()), ("peek", ())]),
            S("cancel_then_reprioritize_raises", [("submit", ("a", 1)), ("cancel", ("a",)),
                                                  ("reprioritize", ("a", 5)), ("priority_of", ("a",)),
                                                  ("cancel", ("a",)), ("len", ())]),
            S("popped_task_not_active", [("submit", ("a", 1)), ("pop", ()), ("cancel", ("a",)),
                                         ("reprioritize", ("a", 2)), ("priority_of", ("a",)), ("len", ())]),
            S("resubmit_after_pop_fresh_fifo", [("submit", ("a", 5)), ("submit", ("b", 5)), ("pop", ()),
                                                ("submit", ("a", 5)), ("pop", ()), ("pop", ())]),
            S("resubmit_after_cancel_old_priority_gone", [("submit", ("a", 99)), ("cancel", ("a",)),
                                                          ("submit", ("b", 10)), ("submit", ("a", 1)), ("pop", ()),
                                                          ("pop", ()), ("pop", ())]),
            S("many_reprioritize_same_task", [("submit", ("x", 0)), ("submit", ("y", 5))] +
              [("reprioritize", ("x", p)) for p in [10, 1, 7, 3, 6, 5]] + [("pop", ()), ("pop", ()), ("len", ())]),
            S("int_ids_and_negative_priorities", [("submit", (3, -5)), ("submit", (1, -5)), ("submit", (2, -10**12)),
                                                  ("submit", (0, 10**12)), ("pop", ()), ("pop", ()), ("pop", ()),
                                                  ("pop", ()), ("pop", ())]),
            S("peek_is_idempotent", [("submit", ("a", 1)), ("submit", ("b", 2)), ("peek", ()), ("peek", ()),
                                     ("len", ()), ("pop", ()), ("peek", ())]),
            S("cancel_all_then_empty", [("submit", ("t%d" % i, i % 3)) for i in range(6)] +
              [("cancel", ("t%d" % i,)) for i in range(6)] + [("len", ()), ("peek", ()), ("pop", ())]),
        ]
        for k in range(18):
            ids = ["t%d" % i for i in range(rng.randint(2, 16))]
            lo = rng.choice([-5, 0])
            ops = sched_ops(rng, rng.randint(40, 150), ids, lo, lo + rng.choice([1, 3, 20])) + [("len", ())]
            out.append(S("random_script_%02d" % k, ops))
        out.append(case("stress_100k_ops_wide_priorities", STRESS_SCHED % (1, 50000, 10**6, 50000, 10**6), timeout_s=10))
        out.append(case("stress_100k_ops_few_priorities", STRESS_SCHED % (2, 50000, 4, 50000, 4), timeout_s=10))
        return out


# ---------------------------------------------------------------------------------------------
# UndoStack
# ---------------------------------------------------------------------------------------------
class RefUndo:
    """Snapshot reference: history keeps a copy of the whole stack before each successful op."""

    def __init__(self):
        self.items = []
        self.snaps = []

    def push(self, x):
        self.snaps.append(list(self.items))
        self.items.append(x)

    def pop(self):
        if not self.items:
            raise IndexError("empty")
        self.snaps.append(list(self.items))
        return self.items.pop()

    def peek(self):
        if not self.items:
            raise IndexError("empty")
        return self.items[-1]

    def undo(self):
        if not self.snaps:
            raise RuntimeError("nothing")
        self.items = self.snaps.pop()

    def __len__(self):
        return len(self.items)


UNDO_VALUES = [0, 1, 1, None, "a", "", (1,), [2, 3], {"k": 1}, 2.5, False]


def undo_ops(rng, n):
    ops = []
    for _ in range(n):
        r = rng.random()
        if r < 0.4:
            ops.append(("push", (rng.choice(UNDO_VALUES),)))
        elif r < 0.65:
            ops.append(("pop", ()))
        elif r < 0.75:
            ops.append(("peek", ()))
        elif r < 0.93:
            ops.append(("undo", ()))
        else:
            ops.append(("len", ()))
    return ops


IDENTITY_UNDO = r'''
s = sol.UndoStack()
x = [1, 2]
y = {"a": []}
s.push(x); s.push(y)
r = [s.pop() is y, s.pop() is x]
s.undo(); s.undo()
r += [s.peek() is y, s.pop() is y, s.peek() is x]
s.undo()
r += [s.peek() is y, len(s)]
result = r
'''


@register("undoable-stack")
class Undo:
    note = "snapshot reference: whole-stack copies pushed on every successful push/pop"
    n_cross = 600
    call = staticmethod(make_call(("push", "undo")))
    brute = RefUndo

    def gen(rng):
        return ((), undo_ops(rng, rng.randint(1, 50)))

    def cases(rng):
        S = lambda name, ops: script_case(name, "UndoStack", (), ops, ("push", "undo"))
        out = [
            S("undo_on_fresh_stack", [("undo", ()), ("len", ()), ("push", (1,)), ("undo", ()), ("undo", ()),
                                      ("len", ())]),
            S("failed_pops_not_recorded", [("push", ("a",)), ("pop", ()), ("pop", ()), ("pop", ()), ("undo", ()),
                                           ("peek", ()), ("undo", ()), ("len", ()), ("undo", ())]),
            S("failed_peek_not_recorded", [("peek", ()), ("push", (5,)), ("undo", ()), ("peek", ()), ("undo", ())]),
            S("undo_three_pops_reverse_order", [("push", (i,)) for i in range(5)] +
              [("pop", ()), ("pop", ()), ("pop", ()), ("undo", ()), ("peek", ()), ("undo", ()), ("peek", ()),
               ("undo", ()), ("peek", ()), ("len", ()), ("pop", ()), ("pop", ()), ("pop", ()), ("pop", ()),
               ("pop", ()), ("pop", ())]),
            S("alternating_push_pop_full_unwind", [("push", ("a",)), ("pop", ()), ("push", ("b",)), ("pop", ()),
                                                   ("push", ("c",)), ("len", ())] +
              [x for _ in range(5) for x in [("undo", ()), ("len", ())]] + [("peek", ()), ("undo", ()),
                                                                             ("len", ()), ("undo", ())]),
            S("none_values_distinguished", [("push", (None,)), ("push", (None,)), ("len", ()), ("peek", ()),
                                            ("pop", ()), ("undo", ()), ("len", ()), ("pop", ()), ("pop", ()),
                                            ("pop", ())]),
            S("falsy_values", [("push", (0,)), ("push", (False,)), ("push", ("",)), ("push", ([],)), ("pop", ()),
                               ("pop", ()), ("undo", ()), ("undo", ()), ("pop", ()), ("pop", ()), ("pop", ()),
                               ("pop", ())]),
            S("unhashable_values", [("push", ([1],)), ("push", ({"a": 1},)), ("push", ({2},)), ("pop", ()),
                                    ("undo", ()), ("peek", ()), ("len", ())]),
            S("undo_push_after_undone_pop", [("push", (1,)), ("push", (2,)), ("pop", ()), ("undo", ()),
                                             ("undo", ()), ("peek", ()), ("len", ()), ("undo", ()), ("len", ()),
                                             ("undo", ())]),
            S("push_after_undo_then_undo_again", [("push", ("a",)), ("push", ("b",)), ("undo", ()),
                                                  ("push", ("c",)), ("pop", ()), ("undo", ()), ("peek", ()),
                                                  ("undo", ()), ("peek", ()), ("undo", ()), ("len", ())]),
            case("popped_object_identity_restored", IDENTITY_UNDO),
        ]
        for k in range(20):
            out.append(S("random_script_%02d" % k, undo_ops(rng, rng.randint(40, 160)) + [("len", ())]))
        return out


# ---------------------------------------------------------------------------------------------
# VersionedKV
# ---------------------------------------------------------------------------------------------
class RefKV:
    """Reference storing each snapshot as a list of (key, value) pairs."""

    def __init__(self):
        self.work = []        # list of [key, value]
        self.snaps = [[]]

    def _idx(self, k):
        for i, (kk, _) in enumerate(self.work):
            if kk == k:
                return i
        return -1

    def set(self, k, v):
        i = self._idx(k)
        if i >= 0:
            self.work[i] = [k, v]
        else:
            self.work.append([k, v])

    def delete(self, k):
        i = self._idx(k)
        if i < 0:
            raise KeyError(k)
        self.work.pop(i)

    def get(self, k):
        i = self._idx(k)
        if i < 0:
            raise KeyError(k)
        return self.work[i][1]

    def has(self, k):
        return self._idx(k) >= 0

    def commit(self):
        self.snaps.append([tuple(p) for p in self.work])
        return len(self.snaps) - 1

    def get_at(self, k, v):
        if not (1 <= v <= len(self.snaps) - 1):
            raise ValueError(v)
        for kk, vv in self.snaps[v]:
            if kk == k:
                return vv
        raise KeyError(k)

    def rollback(self, v):
        if not (0 <= v <= len(self.snaps) - 1):
            raise ValueError(v)
        self.work = [list(p) for p in self.snaps[v]]

    def latest(self):
        return len(self.snaps) - 1


def kv_ops(rng, n, keys):
    ops, latest = [], 0
    for i in range(n):
        r = rng.random()
        k = rng.choice(keys)
        if r < 0.3:
            ops.append(("set", (k, rng.choice([i, None, "s%d" % i, 0]))))
        elif r < 0.4:
            ops.append(("delete", (k,)))
        elif r < 0.5:
            ops.append(("get", (k,)))
        elif r < 0.56:
            ops.append(("has", (k,)))
        elif r < 0.68:
            ops.append(("commit", ()))
            latest += 1
        elif r < 0.82:
            ops.append(("get_at", (k, rng.randint(-1, latest + 1))))
        elif r < 0.92:
            ops.append(("rollback", (rng.randint(-1, latest + 1),)))
        else:
            ops.append(("latest", ()))
    return ops


@register("versioned-key-value-store-with-rollback")
class KV:
    note = "reference: working state and snapshots as (key, value) pair lists, linear lookups"
    n_cross = 600
    call = staticmethod(make_call(("set", "delete", "rollback")))
    brute = RefKV

    def gen(rng):
        keys = ["k%d" % i for i in range(rng.randint(1, 6))]
        return ((), kv_ops(rng, rng.randint(1, 50), keys))

    def cases(rng):
        S = lambda name, ops: script_case(name, "VersionedKV", (), ops, ("set", "delete", "rollback"))
        out = [
            S("fresh_store", [("latest", ()), ("has", ("a",)), ("get", ("a",)), ("delete", ("a",)),
                              ("get_at", ("a", 0)), ("get_at", ("a", 1)), ("rollback", (0,)), ("rollback", (1,)),
                              ("latest", ())]),
            S("rollback_zero_without_commits", [("set", ("a", 1)), ("rollback", (0,)), ("has", ("a",)),
                                                ("latest", ()), ("commit", ()), ("get_at", ("a", 1))]),
            S("overwrite_before_commit", [("set", ("a", 1)), ("set", ("a", 2)), ("commit", ()), ("get_at", ("a", 1)),
                                          ("set", ("a", 3)), ("get_at", ("a", 1)), ("get", ("a",))]),
            S("delete_then_set_again", [("set", ("a", 1)), ("delete", ("a",)), ("has", ("a",)), ("set", ("a", 2)),
                                        ("commit", ()), ("get_at", ("a", 1)), ("delete", ("a",)), ("delete", ("a",)),
                                        ("get_at", ("a", 1))]),
            S("none_value_present", [("set", ("n", None)), ("has", ("n",)), ("get", ("n",)), ("commit", ()),
                                     ("get_at", ("n", 1)), ("delete", ("n",)), ("get_at", ("n", 1)),
                                     ("has", ("n",))]),
            S("rollback_to_latest_discards_uncommitted", [("set", ("a", 1)), ("commit", ()), ("set", ("a", 2)),
                                                          ("set", ("b", 3)), ("rollback", (1,)), ("get", ("a",)),
                                                          ("has", ("b",)), ("latest", ())]),
            S("rollback_does_not_create_version", [("set", ("a", 1)), ("commit", ()), ("commit", ()),
                                                   ("rollback", (1,)), ("rollback", (0,)), ("latest", ()),
                                                   ("commit", ()), ("get_at", ("a", 3)), ("get_at", ("a", 2))]),
            S("rollback_bounds", [("commit", ()), ("commit", ()), ("rollback", (3,)), ("rollback", (-1,)),
                                  ("rollback", (2,)), ("latest", ())]),
            S("get_at_bounds_after_rollback", [("set", ("a", 1)), ("commit", ()), ("set", ("a", 2)), ("commit", ()),
                                               ("rollback", (1,)), ("get_at", ("a", 2)), ("get_at", ("a", 3)),
                                               ("get_at", ("a", 0)), ("commit", ()), ("get_at", ("a", 3))]),
            S("mutation_after_rollback_isolated", [("set", ("a", 1)), ("commit", ()), ("rollback", (1,)),
                                                   ("set", ("a", 5)), ("delete", ("a",)), ("get_at", ("a", 1)),
                                                   ("rollback", (1,)), ("get", ("a",))]),
            S("many_keys_mixed_types", [("set", (1, "int")), ("set", ("1", "str")), ("set", ((1,), "tuple")),
                                        ("commit", ()), ("delete", (1,)), ("commit", ()), ("get_at", (1, 1)),
                                        ("get_at", ("1", 2)), ("get_at", (1, 2)), ("get_at", ((1,), 2))]),
            S("unicode_keys_and_values", [("set", ("clé", "valeur")), ("set", ("键", "值")), ("commit", ()),
                                          ("get_at", ("键", 1)), ("get", ("clé",))]),
            S("deep_history_reads", [x for i in range(12) for x in [("set", ("k", i)), ("commit", ())]] +
              [("get_at", ("k", v)) for v in range(1, 13)] + [("rollback", (5,)), ("get", ("k",)), ("commit", ()),
                                                              ("get_at", ("k", 13))]),
        ]
        for k in range(20):
            keys = ["k%d" % i for i in range(rng.randint(2, 8))]
            out.append(S("random_script_%02d" % k, kv_ops(rng, rng.randint(40, 150), keys) + [("latest", ())]))
        return out
