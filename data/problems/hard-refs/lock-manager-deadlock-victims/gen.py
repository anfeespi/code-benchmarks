N = 800


def gen(rng):
    ntx = rng.randint(1, 8)
    res = ["r%d" % k for k in range(rng.randint(1, 3))] + (["a"] if rng.random() < 0.3 else [])
    ops = []
    for _ in range(rng.randint(0, 22)):
        tx = rng.randint(1, ntx)
        k = rng.random()
        if k < 0.12:
            ops.append(("COMMIT", tx))
        else:
            ops.append(("S" if rng.random() < 0.5 else "X", tx, rng.choice(res)))
    return (ops,)
