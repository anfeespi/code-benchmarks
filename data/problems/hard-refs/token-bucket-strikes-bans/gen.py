N = 600


def gen(rng):
    gcap = rng.randint(1, 6)
    cfg = {"cap": rng.randint(1, 4), "period": rng.randint(1, 6), "gcap": gcap, "gperiod": rng.randint(1, 6),
           "reserve": rng.randint(0, gcap), "strikes": rng.randint(1, 3), "window": rng.randint(1, 8),
           "ban": rng.randint(1, 8)}
    clients = ["c%d" % k for k in range(rng.randint(1, 3))]
    n = rng.randint(0, 30)
    t = rng.randint(0, 3)
    reqs = []
    for _ in range(n):
        t += rng.choice([0, 0, 1, 1, 2, 3, cfg["period"], cfg["window"], cfg["ban"]])
        reqs.append((t, rng.choice(clients), rng.choice([1, 1, 1, 2, 3, 5]), rng.random() < 0.3))
    if n >= 2 and rng.random() < 0.04:
        reqs[0], reqs[-1] = reqs[-1], reqs[0]
    return (reqs, cfg)
