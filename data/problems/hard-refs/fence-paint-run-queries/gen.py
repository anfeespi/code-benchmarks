N = 600


def gen(rng):
    n = rng.randint(1, 14)
    k = rng.randint(1, 4)
    colors = [rng.randint(0, k - 1) for _ in range(n)]
    ops = []
    for _ in range(rng.randint(0, 14)):
        l = rng.randint(0, n - 1)
        r = rng.randint(l, n - 1)
        if rng.random() < 0.5:
            ops.append(("paint", l, r, rng.randint(0, k)))
        else:
            ops.append(("query", l, r))
    return (colors, ops)
