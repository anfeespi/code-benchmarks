N = 600


def make_network(rng, n_st, n_trips, max_len, horizon):
    conns = []
    for tid in range(n_trips):
        x = rng.randrange(n_st)
        t = rng.randint(0, horizon)
        for _ in range(rng.randint(1, max_len)):
            y = rng.randrange(n_st - 1)
            if y >= x:
                y += 1
            d = rng.randint(1, 5)
            conns.append((tid * 3 + 7, x, y, t, t + d))
            t = t + d + rng.choice([0, 0, 1, 2, 4])
            x = y
    rng.shuffle(conns)
    return conns


def gen(rng):
    n_st = rng.randint(2, 6)
    conns = make_network(rng, n_st, rng.randint(0, 6), 4, 15)
    transfer = [rng.choice([0, 0, 1, 2, 3, 6]) for _ in range(n_st)]
    k = rng.choice([0, 1, 1, 2, 2, 3, 4, 10 ** 9])
    return (conns, transfer, rng.randrange(n_st), rng.randrange(n_st), rng.randint(0, 8), k)
