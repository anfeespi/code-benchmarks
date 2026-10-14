N = 600


def gen(rng):
    labels = ["a", "b", "c"][: rng.randint(1, 3)]
    lo, hi = -6, rng.choice([6, 12, 20])
    ops = []
    for _ in range(rng.randint(0, 30)):
        k = rng.random()
        l, r = rng.randint(lo, hi), rng.randint(lo, hi)
        if rng.random() < 0.85 and l > r:
            l, r = r, l
        if k < 0.35:
            ops.append(("paint", l, r, rng.choice(labels)))
        elif k < 0.5:
            ops.append(("erase", l, r))
        elif k < 0.62:
            ops.append(("at", rng.randint(lo - 2, hi + 2)))
        elif k < 0.74:
            ops.append(("runs",))
        elif k < 0.86:
            ops.append(("total", rng.choice(labels + ["zz"])))
        else:
            ops.append(("next_change", rng.randint(lo - 2, hi + 2)))
    return (ops,)
