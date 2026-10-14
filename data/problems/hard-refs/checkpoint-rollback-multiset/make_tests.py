"""Writes tests/hard/checkpoint-rollback-multiset.json (cases only; expected values come from
`python -m codebench.hard_tools build checkpoint-rollback-multiset`)."""
import json
from pathlib import Path

SLUG = "checkpoint-rollback-multiset"
S = ("result = (len(out), sum(x for x in out if type(x) is int) % 1000000007, out.count(None), "
     "out.count('BADCP'), sum(1 for x in out if x is True), out[::4001])")
cases = [
    ("example_1", "result = sol.run_ops([('add', 5), ('add', 1), ('checkpoint',), ('add', 9), ('add', 9), ('median',), ('rollback', 1), ('median',), ('distinct',), ('count_less', 5)])"),
    ("example_2", "result = sol.run_ops([('checkpoint',), ('add', 3), ('checkpoint',), ('remove', 3), ('checkpoint',), ('rollback', 2), ('rollback', 3), ('checkpoint',), ('rollback', 1), ('rollback', 4), ('rollback', 1), ('remove', 3), ('median',)])"),
    ("empty", "result = sol.run_ops([])"),
    ("queries_on_empty", "result = sol.run_ops([('median',), ('count_less', 0), ('distinct',), ('remove', 0), ('rollback', 0), ('rollback', 1), ('rollback', -1)])"),
    ("duplicates_and_lower_median", "result = sol.run_ops([('add', 4), ('add', 4), ('add', 2), ('median',), ('add', 8), ('median',), ('distinct',), ('remove', 4), ('median',), ('distinct',), ('remove', 4), ('distinct',), ('remove', 4), ('count_less', 5)])"),
    ("rollback_to_same_twice", "result = sol.run_ops([('add', 1), ('checkpoint',), ('add', 2), ('rollback', 1), ('add', 3), ('add', 4), ('rollback', 1), ('median',), ('distinct',), ('rollback', 1)])"),
    ("rollback_invalidates_later_only", "result = sol.run_ops([('checkpoint',), ('add', 1), ('checkpoint',), ('add', 2), ('checkpoint',), ('add', 3), ('rollback', 2), ('rollback', 1), ('rollback', 3), ('rollback', 2), ('rollback', 1), ('checkpoint',), ('add', 7), ('rollback', 4), ('median',)])"),
    ("checkpoint_ids_never_reused", "result = sol.run_ops([('checkpoint',), ('checkpoint',), ('checkpoint',), ('rollback', 1), ('checkpoint',), ('rollback', 2), ('rollback', 4), ('checkpoint',)])"),
    ("failed_remove_not_logged", "result = sol.run_ops([('add', 1), ('checkpoint',), ('remove', 2), ('remove', 1), ('remove', 1), ('add', 2), ('rollback', 1), ('count_less', 2), ('median',), ('distinct',)])"),
    ("rollback_restores_removed", "result = sol.run_ops([('add', x) for x in [5, 3, 5, 1]] + [('checkpoint',), ('remove', 5), ('remove', 5), ('remove', 3), ('distinct',), ('rollback', 1), ('distinct',), ('median',), ('count_less', 6)])"),
    ("checkpoint_of_empty", "result = sol.run_ops([('checkpoint',), ('add', 10), ('add', -10), ('checkpoint',), ('rollback', 1), ('median',), ('rollback', 2), ('add', 0), ('rollback', 1), ('distinct',)])"),
    ("extreme_values", "result = sol.run_ops([('add', -10**9), ('add', 10**9), ('median',), ('count_less', 10**9), ('count_less', -10**9), ('count_less', 10**9 + 1), ('remove', 10**9 + 1)])"),
]
RAND = """import random
r = random.Random({seed})
ops = []
valid = []
nid = 1
for _ in range({n}):
    x = r.random()
    if x < 0.32: ops.append(('add', r.randint(-{vr}, {vr})))
    elif x < 0.45: ops.append(('remove', r.randint(-{vr}, {vr})))
    elif x < 0.55:
        ops.append(('checkpoint',)); valid.append(nid); nid += 1
    elif x < 0.65:
        c = r.choice(valid) if valid and r.random() < 0.8 else r.randint(-1, nid + 1)
        ops.append(('rollback', c))
        if c in valid: valid = [v for v in valid if v <= c]
    elif x < 0.77: ops.append(('median',))
    elif x < 0.9: ops.append(('count_less', r.randint(-{vr}, {vr})))
    else: ops.append(('distinct',))
result = sol.run_ops(ops)"""
for seed, (n, vr) in enumerate([(40, 3), (100, 10), (400, 50), (3000, 200), (8000, 10**9)]):
    cases.append(("random_%d" % (seed + 1), RAND.format(seed=300 + seed, n=n, vr=vr)))

cases.append(("stress_checkpoint_per_step", """import random, bisect
r = random.Random(41)
ops = [('add', r.randint(-10**9, 10**9)) for _ in range(100000)]
valid = []
nid = 1
while len(ops) < 300000:
    ops.append(('checkpoint',)); valid.append(nid); nid += 1
    for _ in range(r.randint(1, 3)):
        ops.append(('add', r.randint(-10**9, 10**9)) if r.random() < 0.6 else ('remove', ops[r.randint(0, 99999)][1]))
    ops.append(('median',) if r.random() < 0.5 else ('count_less', r.randint(-10**9, 10**9)))
    if r.random() < 0.7:
        c = valid[-1] if r.random() < 0.9 else r.choice(valid)
        ops.append(('rollback', c)); del valid[bisect.bisect_right(valid, c):]
out = sol.run_ops(ops)
""" + S, 6))
cases.append(("stress_long_undo_runs", """import random
r = random.Random(42)
ops = [('add', r.randint(0, 10**6)) for _ in range(100000)]
ops.append(('checkpoint',))
for rnd in range(120):
    for _ in range(1500):
        ops.append(('add', r.randint(0, 10**6)))
    ops.append(('median',)); ops.append(('distinct',))
    ops.append(('rollback', 1))
    ops.append(('median',))
for _ in range(10000):
    ops.append(('count_less', r.randint(0, 10**6)))
out = sol.run_ops(ops)
""" + S, 6))
cases.append(("stress_deep_rollbacks_and_queries", """import random, bisect
r = random.Random(43)
ops = []
valid = []
nid = 1
for i in range(120000):
    ops.append(('add', r.randint(-5000, 5000)))
    if i % 10 == 0:
        ops.append(('checkpoint',)); valid.append(nid); nid += 1
while len(ops) < 300000:
    x = r.random()
    if x < 0.003 and valid:
        c = valid[max(0, len(valid) - 1 - r.randint(0, 2000))]
        ops.append(('rollback', c)); del valid[bisect.bisect_right(valid, c):]
    elif x < 0.3: ops.append(('median',))
    elif x < 0.6: ops.append(('count_less', r.randint(-6000, 6000)))
    elif x < 0.7: ops.append(('distinct',))
    elif x < 0.85: ops.append(('add', r.randint(-5000, 5000)))
    elif x < 0.95: ops.append(('remove', r.randint(-5000, 5000)))
    else:
        ops.append(('checkpoint',)); valid.append(nid); nid += 1
out = sol.run_ops(ops)
""" + S, 6))

root = Path(__file__).resolve().parents[4]
t = {"title": "Checkpoint and rollback multiset with order statistics", "entry_point": "run_ops",
     "cases": [dict(name=c[0], code=c[1], **({"timeout_s": c[2]} if len(c) > 2 else {})) for c in cases]}
(root / "tests" / "hard" / (SLUG + ".json")).write_text(json.dumps(t, indent=1) + "\n")
print(len(cases), "cases")
