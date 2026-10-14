N = 500


def gen(rng):
    n = rng.randint(0, 25)
    players = ["p%d" % k for k in range(rng.randint(1, 6))]
    lo, hi = sorted((rng.randint(-5, 5), rng.randint(-5, 5)))
    return ([(rng.choice(players), rng.randint(lo, hi)) for _ in range(n)],)
