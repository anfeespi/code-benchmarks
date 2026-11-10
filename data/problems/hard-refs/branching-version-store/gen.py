N = 600


def gen(rng):
    ops = []
    nver = 1
    kr = rng.choice([3, 6, 12])
    for _ in range(rng.randint(0, 30)):
        x = rng.random()
        v = rng.randint(-1, nver + 1) if rng.random() < 0.12 else rng.randint(0, nver - 1)
        if x < 0.35:
            ops.append(("set", v, rng.randint(-kr, kr), rng.randint(-5, 5)))
            if 0 <= v < nver:
                nver += 1
        elif x < 0.5:
            ops.append(("del", v, rng.randint(-kr, kr)))
        elif x < 0.62:
            ops.append(("get", v, rng.randint(-kr - 1, kr + 1)))
        elif x < 0.74:
            a = rng.randint(-kr - 2, kr + 2)
            ops.append(("count", v, a, a + rng.randint(-2, 2 * kr)))
        elif x < 0.86:
            a = rng.randint(-kr - 2, kr + 2)
            ops.append(("sum", v, a, a + rng.randint(-2, 2 * kr)))
        else:
            ops.append(("kth", v, rng.randint(-1, 2 * kr)))
    return (ops,)
