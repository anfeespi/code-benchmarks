N = 600


def gen(rng):
    cap = rng.randint(1, 4)
    keys = ["k%d" % i for i in range(rng.randint(1, 6))]
    t = rng.randint(0, 3)
    ops = []
    for _ in range(rng.randint(0, 30)):
        t += rng.choice([0, 0, 1, 1, 2, 3])
        r = rng.random()
        if r < 0.5:
            ttl = rng.choice([None, None, 1, 2, 3, 4, 6])
            ops.append(("put", t, rng.choice(keys), rng.randint(0, 9), ttl))
        elif r < 0.85:
            ops.append(("get", t, rng.choice(keys)))
        else:
            ops.append(("size", t))
    if rng.random() < 0.03:
        cap = rng.choice([0, -1])
    if rng.random() < 0.03 and ops:
        ops.append(("get", -1, "k0"))
    return (cap, ops)
