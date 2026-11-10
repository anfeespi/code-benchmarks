N = 800


def gen(rng):
    n = rng.randint(0, 30)
    lo, hi = sorted((rng.randint(-4, 4), rng.randint(-4, 4)))
    p_none = rng.choice([0.0, 0.1, 0.3, 0.6])
    readings = [None if rng.random() < p_none else rng.randint(lo, hi) for _ in range(n)]
    k = rng.randint(1, 8) if rng.random() < 0.97 else rng.choice([0, -2])
    return (readings, k)
