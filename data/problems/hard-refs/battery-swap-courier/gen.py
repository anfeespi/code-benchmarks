N = 600


def gen(rng):
    n = rng.randint(1, 6)
    cap = rng.randint(0, 6)
    roads = []
    for _ in range(rng.randint(0, 12)):
        u, v = rng.randrange(n), rng.randrange(n)
        e = rng.randint(-cap, cap) if rng.random() < 0.9 else 0
        roads.append((u, v, rng.choice([0, 0, 1, 2, 3, 5, 8]), e))
    stations = [rng.randrange(n) for _ in range(rng.randint(0, 3))]
    return (n, roads, stations, cap, rng.choice([0, 0, 1, 2, 4, 10]), rng.randint(0, 3),
            rng.randrange(n), rng.randrange(n))
