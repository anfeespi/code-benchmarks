"""Writes tests/hard/branching-version-store.json (cases only; expected values come from
`python -m codebench.hard_tools build branching-version-store`)."""
import json
from pathlib import Path

SLUG = "branching-version-store"
S = ("result = (len(out), sum(x for x in out if type(x) is int) % 1000000007, out.count(None), "
     "out.count('BADVER'), out.count('NOKEY'), out[::2503])")
cases = [
    ("example_1", "result = sol.run_ops([('set', 0, 5, 50), ('set', 1, 2, 20), ('set', 1, 9, 90), ('kth', 2, 1), ('kth', 3, 1), ('sum', 3, 0, 10), ('get', 2, 9), ('get', 0, 5)])"),
    ("example_2", "result = sol.run_ops([('del', 0, 7), ('set', 0, 7, 1), ('del', 1, 7), ('del', 2, 7), ('count', 2, -10, 10), ('count', 1, 7, 7), ('get', 3, 7), ('kth', 9, 1)])"),
    ("empty", "result = sol.run_ops([])"),
    ("queries_on_version_zero", "result = sol.run_ops([('get', 0, 1), ('count', 0, -10**9, 10**9), ('sum', 0, -5, 5), ('kth', 0, 1), ('kth', 0, 0), ('del', 0, 3)])"),
    ("badver_boundaries", "result = sol.run_ops([('get', -1, 0), ('set', 1, 0, 0), ('set', 0, 0, 0), ('get', 1, 0), ('get', 2, 0), ('set', 2, 1, 1), ('set', 1, 1, 1), ('kth', 2, 2), ('del', -5, 0)])"),
    ("overwrite_same_value_still_new_version", "result = sol.run_ops([('set', 0, 4, 4), ('set', 1, 4, 4), ('set', 2, 4, 5), ('get', 1, 4), ('get', 2, 4), ('get', 3, 4), ('count', 3, 4, 4)])"),
    ("value_zero_vs_absent", "result = sol.run_ops([('set', 0, 3, 0), ('get', 1, 3), ('get', 1, 4), ('count', 1, 3, 3), ('sum', 1, 3, 3), ('del', 1, 3), ('get', 2, 3), ('del', 2, 3)])"),
    ("negative_values_sum", "result = sol.run_ops([('set', 0, -1, -10), ('set', 1, 1, 7), ('set', 2, 0, -3), ('sum', 3, -1, 1), ('sum', 3, 0, 0), ('sum', 3, 1, -1), ('count', 3, 1, -1)])"),
    ("kth_bounds", "result = sol.run_ops([('set', 0, 10, 1), ('set', 1, -10, 1), ('set', 2, 0, 1), ('kth', 3, 1), ('kth', 3, 2), ('kth', 3, 3), ('kth', 3, 4), ('kth', 3, -1), ('kth', 3, 10**9)])"),
    ("branch_isolation", "result = sol.run_ops([('set', 0, 1, 1), ('set', 1, 2, 2), ('set', 1, 3, 3), ('set', 2, 4, 4), ('del', 3, 1), ('count', 4, 0, 10), ('count', 5, 0, 10), ('kth', 5, 1), ('kth', 4, 3), ('get', 5, 2), ('get', 4, 3), ('count', 1, 0, 10)])"),
    ("delete_then_reinsert_old_branch", "result = sol.run_ops([('set', 0, 8, 80), ('del', 1, 8), ('set', 2, 8, 81), ('get', 1, 8), ('get', 2, 8), ('get', 3, 8), ('del', 2, 8), ('del', 3, 8), ('get', 4, 8)])"),
    ("query_keys_never_stored", "result = sol.run_ops([('set', 0, 100, 1), ('set', 1, 300, 3), ('count', 2, 101, 299), ('count', 2, 100, 300), ('sum', 2, 99, 101), ('get', 2, 200), ('del', 2, 200)])"),
    ("extreme_keys", "result = sol.run_ops([('set', 0, -10**9, 10**9), ('set', 1, 10**9, -10**9), ('sum', 2, -10**9, 10**9), ('kth', 2, 2), ('count', 2, 10**9, 10**9)])"),
]
for seed, (n, kr) in enumerate([(40, 5), (100, 10), (400, 30), (3000, 200), (6000, 2000)]):
    cases.append(("random_%d" % (seed + 1), f"""import random
r = random.Random({200 + seed})
ops = []
nv = 1
for _ in range({n}):
    x = r.random(); v = r.randint(-1, nv + 1) if r.random() < 0.05 else max(0, nv - 1 - int(r.expovariate(0.3)))
    if x < 0.35:
        ops.append(('set', v, r.randint(-{kr}, {kr}), r.randint(-100, 100)))
        nv += 1 if 0 <= v < nv else 0
    elif x < 0.5: ops.append(('del', v, r.randint(-{kr}, {kr})))
    elif x < 0.62: ops.append(('get', v, r.randint(-{kr}, {kr})))
    elif x < 0.74:
        a = r.randint(-{kr}, {kr}); ops.append(('count', v, a, a + r.randint(-3, {kr})))
    elif x < 0.86:
        a = r.randint(-{kr}, {kr}); ops.append(('sum', v, a, a + r.randint(-3, {kr})))
    else: ops.append(('kth', v, r.randint(0, {kr})))
result = sol.run_ops(ops)"""))

STRESS_GEN = """import random
r = random.Random({seed})
ops = []
nv = 1
for i in range({n}):
    x = r.random() if i >= {warm} else 0.0
    v = ({vexpr}) if i >= {warm} else nv - 1
    if x < {pset}:
        ops.append(('set', v, r.randint(-{kr}, {kr}), r.randint(-10**6, 10**6))); nv += 1
    elif x < {pdel}: ops.append(('del', v, r.randint(-{kr}, {kr})))
    elif x < 0.80: ops.append(('get', v, r.randint(-{kr}, {kr})))
    elif x < 0.87:
        a = r.randint(-{kr}, {kr}); ops.append(('count', v, a, a + r.randint(0, {kr})))
    elif x < 0.94:
        a = r.randint(-{kr}, {kr}); ops.append(('sum', v, a, a + r.randint(0, {kr})))
    else: ops.append(('kth', v, r.randint(1, 40000)))
out = sol.run_ops(ops)
"""
# nv only counts versions created by sets (successful dels also create versions), so v stays valid

# chain: always derive from the newest set-version -> versions grow to tens of thousands of keys
cases.append(("stress_long_chain", STRESS_GEN.format(seed=31, n=150000, vexpr="nv - 1", warm=40000, pset=0.3, pdel=0.7, kr=10**6) + S, 10))
# branching: derive from a random recent-ish version
cases.append(("stress_branching", STRESS_GEN.format(seed=32, n=150000, vexpr="max(0, nv - 1 - int(r.expovariate(0.001)))", warm=40000,
                                                    pset=0.4, pdel=0.6, kr=10**6) + S, 10))
# dense keys, delete heavy, queries on random old versions
cases.append(("stress_dense_deletes", STRESS_GEN.format(seed=33, n=150000, vexpr="r.randint(0, nv - 1) if i % 2 else nv - 1", warm=30000,
                                                        pset=0.3, pdel=0.6, kr=40000) + S, 10))

root = Path(__file__).resolve().parents[4]
t = {"title": "Branching version store with range and rank queries", "entry_point": "run_ops",
     "cases": [dict(name=c[0], code=c[1], **({"timeout_s": c[2]} if len(c) > 2 else {})) for c in cases]}
(root / "tests" / "hard" / (SLUG + ".json")).write_text(json.dumps(t, indent=1) + "\n")
print(len(cases), "cases")
