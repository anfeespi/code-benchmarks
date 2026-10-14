N = 600


def gen(rng):
    n = rng.randint(0, 11)
    msgs = []
    for _ in range(n):
        msgs.append((rng.choice([0, 1, 2, 3, 5, 8]), rng.randint(-9, 12), rng.random() < 0.15))
    budget = rng.randint(0, 20)
    max_gap = rng.randint(0, 4)
    if rng.random() < 0.04:
        budget = -rng.randint(1, 3)
    if rng.random() < 0.04:
        max_gap = -1
    return (msgs, budget, max_gap, rng.choice([0, 0, 1, 3, 7, -2, -5]))
