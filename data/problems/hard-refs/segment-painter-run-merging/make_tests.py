"""Writes tests/hard/segment-painter-run-merging.json (cases only; expected values come from
`python -m codebench.hard_tools build segment-painter-run-merging`)."""
import json
from pathlib import Path

SLUG = "segment-painter-run-merging"
S = ("result = (len(out), sum(x for x in out if type(x) is int), out.count(None), "
     "sum(1 for x in out if type(x) is str), out[::3001])")
cases = [
    ("example_1", "result = sol.run_ops([('paint', 0, 5, 'x'), ('paint', 5, 8, 'x'), ('runs',), ('paint', 2, 6, 'y'), ('runs',), ('total', 'x'), ('next_change', 0), ('next_change', 6), ('next_change', 8)])"),
    ("example_2", "result = sol.run_ops([('paint', 1, 4, 'a'), ('paint', 0, 6, 'a'), ('erase', 3, 10), ('at', 2), ('at', 3), ('erase', 5, 5), ('next_change', -7), ('runs',)])"),
    ("empty", "result = sol.run_ops([])"),
    ("queries_on_blank", "result = sol.run_ops([('at', 0), ('runs',), ('total', 'q'), ('next_change', -10**9), ('next_change', 10**9), ('erase', -5, 5)])"),
    ("reversed_ranges_noop", "result = sol.run_ops([('paint', 5, 2, 'a'), ('paint', 3, 3, 'a'), ('erase', 9, 1), ('runs',), ('at', 3)])"),
    ("repaint_same_label_zero", "result = sol.run_ops([('paint', 0, 10, 'k'), ('paint', 2, 7, 'k'), ('paint', -3, 12, 'k'), ('runs',), ('total', 'k')])"),
    ("adjacent_merge_both_sides", "result = sol.run_ops([('paint', 0, 3, 'a'), ('paint', 6, 9, 'a'), ('runs',), ('paint', 3, 6, 'a'), ('runs',), ('next_change', 0), ('paint', 3, 6, 'b'), ('runs',), ('paint', 3, 6, 'a'), ('runs',)])"),
    ("adjacent_different_labels_not_merged", "result = sol.run_ops([('paint', 0, 2, 'a'), ('paint', 2, 4, 'b'), ('paint', 4, 6, 'a'), ('runs',), ('next_change', 1), ('next_change', 3), ('next_change', 5), ('next_change', 6)])"),
    ("split_inside_run", "result = sol.run_ops([('paint', 0, 100, 'a'), ('erase', 40, 60), ('runs',), ('total', 'a'), ('paint', 40, 60, 'a'), ('runs',), ('total', 'a'), ('erase', 0, 1), ('erase', 99, 100), ('next_change', 0), ('next_change', 1), ('next_change', 98)])"),
    ("erase_spanning_many", "result = sol.run_ops([('paint', i * 3, i * 3 + 2, 'abc'[i % 3]) for i in range(20)] + [('runs',), ('erase', 4, 50), ('runs',), ('total', 'a'), ('total', 'b'), ('total', 'c'), ('next_change', 2), ('next_change', 3)])"),
    ("paint_covers_many_mixed", "result = sol.run_ops([('paint', i, i + 1, 'ab'[i % 2]) for i in range(30)] + [('runs',), ('paint', 5, 25, 'a'), ('runs',), ('total', 'a'), ('total', 'b'), ('paint', 0, 30, 'a'), ('runs',)])"),
    ("negative_and_extreme_coords", "result = sol.run_ops([('paint', -10**9, 10**9, 'w'), ('total', 'w'), ('paint', -1, 1, 'z'), ('runs',), ('next_change', -10**9), ('next_change', -1), ('next_change', 0), ('at', 10**9), ('next_change', 10**9 - 1), ('erase', -10**9, 10**9), ('runs',), ('total', 'w')])"),
    ("total_after_label_vanishes", "result = sol.run_ops([('paint', 0, 4, 'a'), ('paint', 0, 4, 'b'), ('total', 'a'), ('total', 'b'), ('paint', 1, 3, 'a'), ('total', 'a'), ('total', 'b'), ('runs',)])"),
    ("next_change_in_gap", "result = sol.run_ops([('paint', 10, 12, 'a'), ('next_change', 5), ('next_change', 9), ('next_change', 10), ('next_change', 11), ('next_change', 12), ('next_change', 100)])"),
]
for seed, (n, span, nl) in enumerate([(40, 20, 2), (80, 40, 3), (300, 100, 4), (2000, 500, 5), (5000, 3000, 3)]):
    cases.append(("random_%d" % (seed + 1), f"""import random
r = random.Random({100 + seed})
L = ['l%d' % k for k in range({nl})]
ops = []
for _ in range({n}):
    k = r.random(); a = r.randint(-{span}, {span}); b = a + r.randint(-3, {span} // 4)
    if k < 0.4: ops.append(('paint', a, b, r.choice(L)))
    elif k < 0.55: ops.append(('erase', a, b))
    elif k < 0.67: ops.append(('at', a))
    elif k < 0.75: ops.append(('runs',))
    elif k < 0.87: ops.append(('total', r.choice(L)))
    else: ops.append(('next_change', a))
result = sol.run_ops(ops)"""))
cases.append(("stress_fragmenting_paints", """import random
r = random.Random(7)
ops = []
for i in range(200000):
    k = r.random(); a = r.randint(0, 5 * 10**6)
    if k < 0.6: ops.append(('paint', a, a + r.randint(1, 40), 'L%d' % r.randint(0, 4)))
    elif k < 0.7: ops.append(('erase', a, a + r.randint(1, 30)))
    elif k < 0.8: ops.append(('at', a))
    elif k < 0.9: ops.append(('next_change', a))
    else: ops.append(('runs',))
out = sol.run_ops(ops)
""" + S, 20))
cases.append(("stress_wipe_and_rebuild", """import random
r = random.Random(8)
ops = []
for rnd in range(4):
    for i in range(45000):
        a = r.randint(-10**9, 10**9 - 100)
        ops.append(('paint', a, a + r.randint(1, 60), 'ab'[i % 2]))
        if i % 3 == 0: ops.append(('total', 'a'))
    ops.append(('runs',))
    ops.append(('paint', -10**9, 10**9, 'c') if rnd % 2 == 0 else ('erase', -10**9, 10**9))
    ops.append(('runs',))
out = sol.run_ops(ops)
""" + S, 20))
cases.append(("stress_queries_on_many_runs", """import random
r = random.Random(9)
ops = [('paint', 10 * i, 10 * i + 5 + i % 7, 'xyz'[i % 3]) for i in range(70000)]
for _ in range(130000):
    k = r.random(); p = r.randint(-5, 700010)
    ops.append(('at', p) if k < 0.4 else ('next_change', p) if k < 0.8 else ('total', 'xyz'[r.randint(0, 2)]) if k < 0.9 else ('runs',))
out = sol.run_ops(ops)
""" + S, 20))

root = Path(__file__).resolve().parents[4]
t = {"title": "Segment painter with run merging and change counts", "entry_point": "run_ops",
     "cases": [dict(name=c[0], code=c[1], **({"timeout_s": c[2]} if len(c) > 2 else {})) for c in cases]}
(root / "tests" / "hard" / (SLUG + ".json")).write_text(json.dumps(t, indent=1) + "\n")
print(len(cases), "cases")
