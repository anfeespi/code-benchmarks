"""Writes tests/hard/room-booking-first-fit.json (cases only; expected values come from
`python -m codebench.hard_tools build room-booking-first-fit`)."""
import json
from pathlib import Path

SLUG = "room-booking-first-fit"
S = ("result = (len(out), sum(x for x in out if type(x) is int) % 1000000007, sum(1 for x in out if x is True), "
     "out.count('CONFLICT'), out.count('INVALID'), out[::4001])")
cases = [
    ("example_1", "result = sol.run_ops([('book', 0, 4), ('book', 4, 6), ('book', 8, 9), ('book', 5, 7), ('first_fit', 0, 2), ('first_fit', 0, 3), ('first_fit', 5, 1), ('free_between', 2, 12)])"),
    ("example_2", "result = sol.run_ops([('book', 3, 3), ('book', 10, 20), ('cancel', 11), ('first_fit', 12, 5), ('cancel', 10), ('first_fit', 12, 5), ('free_between', 0, 5), ('free_between', 7, 7)])"),
    ("empty", "result = sol.run_ops([])"),
    ("queries_on_empty_calendar", "result = sol.run_ops([('first_fit', 0, 1), ('first_fit', 10**9, 10**9), ('free_between', 0, 10**9), ('free_between', 5, 1), ('cancel', 0)])"),
    ("touching_allowed_overlap_rejected", "result = sol.run_ops([('book', 5, 10), ('book', 10, 12), ('book', 0, 5), ('book', 9, 10), ('book', 11, 13), ('book', 4, 6), ('book', 0, 100), ('book', 12, 13), ('free_between', 0, 13)])"),
    ("first_fit_inside_booking", "result = sol.run_ops([('book', 10, 20), ('first_fit', 10, 1), ('first_fit', 15, 1), ('first_fit', 19, 1), ('first_fit', 20, 1), ('first_fit', 9, 1), ('first_fit', 9, 2), ('first_fit', 0, 10), ('first_fit', 0, 11)])"),
    ("gap_exactly_d", "result = sol.run_ops([('book', 0, 5), ('book', 8, 10), ('book', 13, 20), ('first_fit', 0, 3), ('first_fit', 0, 4), ('first_fit', 6, 3), ('first_fit', 6, 2), ('first_fit', 11, 2), ('first_fit', 11, 3)])"),
    ("skip_many_small_gaps", "result = sol.run_ops([('book', 3 * i, 3 * i + 2) for i in range(50)] + [('first_fit', 0, 1), ('first_fit', 0, 2), ('first_fit', 1, 1), ('first_fit', 77, 2), ('cancel', 60), ('first_fit', 0, 2), ('first_fit', 0, 3), ('first_fit', 0, 4), ('first_fit', 62, 3)])"),
    ("cancel_semantics", "result = sol.run_ops([('book', 2, 9), ('cancel', 3), ('cancel', 9), ('cancel', 2), ('cancel', 2), ('book', 2, 4), ('book', 4, 9), ('cancel', 4), ('free_between', 0, 10)])"),
    ("rebook_same_start_different_end", "result = sol.run_ops([('book', 5, 50), ('cancel', 5), ('book', 5, 7), ('book', 7, 9), ('first_fit', 5, 1), ('book', 5, 50), ('cancel', 5), ('book', 5, 50), ('free_between', 0, 60)])"),
    ("free_between_partial_overlaps", "result = sol.run_ops([('book', 10, 20), ('book', 25, 30), ('book', 40, 41), ('free_between', 15, 27), ('free_between', 12, 18), ('free_between', 20, 25), ('free_between', 0, 100), ('free_between', 29, 41), ('free_between', 30, 40)])"),
    ("huge_coordinates", "result = sol.run_ops([('book', 0, 10**9), ('first_fit', 0, 10**9), ('first_fit', 10**9, 1), ('free_between', 0, 10**9), ('book', 10**9 - 1, 10**9), ('cancel', 0), ('first_fit', 3, 10**9), ('free_between', 10**9 - 5, 10**9)])"),
    ("invalid_and_conflict_change_nothing", "result = sol.run_ops([('book', 7, 3), ('book', 1, 1), ('book', 1, 5), ('book', 0, 2), ('book', 4, 6), ('cancel', 0), ('cancel', 4), ('first_fit', 0, 1), ('first_fit', 0, 2)])"),
]
RAND = """import random
r = random.Random({seed})
ops = []
starts = []
for _ in range({n}):
    x = r.random()
    if x < 0.45:
        s = r.randint(0, {hi}); ops.append(('book', s, s + r.randint(-1, {blen}))); starts.append(s)
    elif x < 0.6: ops.append(('cancel', r.choice(starts) if starts and r.random() < 0.8 else r.randint(0, {hi})))
    elif x < 0.85: ops.append(('first_fit', r.randint(0, {hi}), r.randint(1, {dmax})))
    else:
        a = r.randint(0, {hi}); ops.append(('free_between', a, a + r.randint(-3, {hi} // 3)))
result = sol.run_ops(ops)"""
for seed, (n, hi, blen, dmax) in enumerate([(40, 30, 8, 6), (120, 100, 10, 8), (500, 300, 6, 5), (3000, 2000, 5, 4), (6000, 10**6, 400, 300)]):
    cases.append(("random_%d" % (seed + 1), RAND.format(seed=400 + seed, n=n, hi=hi, blen=blen, dmax=dmax)))

cases.append(("stress_skip_small_gaps", """import random
r = random.Random(51)
ops = []
pos = 0
for i in range(60000):
    ops.append(('book', pos, pos + r.randint(1, 20))); pos = ops[-1][2] + (1 if r.random() < 0.9999 else r.randint(2, 10))
end = pos
for _ in range(140000):
    x = r.random()
    if x < 0.97: ops.append(('first_fit', r.randint(0, end), r.randint(2, 7)))
    else:
        s = r.randint(0, end); ops.append(('book', s, s + r.randint(1, 3)))
out = sol.run_ops(ops)
""" + S, 20))
cases.append(("stress_random_churn", """import random
r = random.Random(52)
ops = []
starts = []
for i in range(200000):
    x = r.random()
    if x < 0.5:
        s = r.randint(0, 3 * 10**6); ops.append(('book', s, s + r.randint(1, 60))); starts.append(s)
    elif x < 0.6: ops.append(('cancel', starts[r.randint(0, len(starts) - 1)] if starts else 0))
    elif x < 0.85: ops.append(('first_fit', r.randint(0, 3 * 10**6), r.randint(1, 200)))
    else:
        a = r.randint(0, 3 * 10**6); ops.append(('free_between', a, a + r.randint(0, 10**6)))
out = sol.run_ops(ops)
""" + S, 20))
cases.append(("stress_wide_free_and_far_fits", """import random
r = random.Random(53)
ops = [('book', 7 * i, 7 * i + 6) for i in range(80000)]
for _ in range(120000):
    x = r.random()
    if x < 0.5: ops.append(('free_between', r.randint(0, 100000), r.randint(400000, 600000)))
    elif x < 0.95: ops.append(('first_fit', r.randint(0, 560000), 9))
    else: ops.append(('cancel', 7 * r.randint(0, 79999)))
out = sol.run_ops(ops)
""" + S, 20))

root = Path(__file__).resolve().parents[4]
t = {"title": "Room booking calendar with first-fit gap search", "entry_point": "run_ops",
     "cases": [dict(name=c[0], code=c[1], **({"timeout_s": c[2]} if len(c) > 2 else {})) for c in cases]}
(root / "tests" / "hard" / (SLUG + ".json")).write_text(json.dumps(t, indent=1) + "\n")
print(len(cases), "cases")
