N = 1000


def gen(rng):
    r = rng.random()
    if r < 0.03:
        return (rng.randint(-5, 5), 0, 10, 2)
    if r < 0.05:
        return (1, 3, rng.choice([0, 1, 37, -3]), 2)
    if r < 0.06:
        return (1, 3, 10, -1)
    base = rng.choice([2, 3, 5, 7, 9, 10, 12, 16, 35, 36, rng.randint(2, 36)])
    k = rng.randint(0, 6)
    if r < 0.5:
        # construct ties deliberately: x = (2m+1) / (2 * base**k), possibly scaled by an odd factor
        m = rng.randint(0, 3 * base ** k + 3)
        f = rng.choice([1, 1, 3, 5])
        p, q = (2 * m + 1) * f, 2 * base ** k * f
    else:
        q = rng.randint(1, 60)
        p = rng.randint(0, 5 * q + 5)
    if rng.random() < 0.5:
        p = -p
    if rng.random() < 0.3:
        q = -q
        p = -p if rng.random() < 0.5 else p
    return (p, q, base, k)
