N = 600


def gen(rng):
    n = rng.randint(1, 18)
    lo = rng.randint(-6, 3)
    hi = lo + rng.randint(0, 9)
    levels = [rng.randint(lo, hi) for _ in range(n)]
    margin = rng.choice([0, 0, 1, 1, 2, 3, rng.randint(0, 12)])
    queries = []
    for _ in range(rng.randint(0, 12)):
        l = rng.randint(0, n - 1)
        queries.append((l, rng.randint(l, n - 1)))
    return (levels, margin, queries)
