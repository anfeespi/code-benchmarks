N = 800


def gen(rng):
    ops = []
    hi = rng.choice([10, 25, 60])
    starts = []
    for _ in range(rng.randint(0, 35)):
        x = rng.random()
        if x < 0.45:
            s = rng.randint(0, hi)
            e = s + rng.randint(-1, hi // 3)
            ops.append(("book", s, e))
            starts.append(s)
        elif x < 0.6:
            ops.append(("cancel", rng.choice(starts) if starts and rng.random() < 0.7 else rng.randint(0, hi)))
        elif x < 0.85:
            ops.append(("first_fit", rng.randint(0, hi + 3), rng.randint(1, hi // 2 + 1)))
        else:
            a = rng.randint(0, hi + 3)
            ops.append(("free_between", a, a + rng.randint(-2, hi)))
    return (ops,)
