N = 700


def gen(rng):
    k = rng.randint(1, 4)
    levels = [rng.choice([0, 5, 50, 80, 95, 100, rng.randint(0, 100)]) for _ in range(k)]
    threshold = rng.choice([1, 50, 60, 90, 100, rng.randint(1, 100)])
    patience = rng.choice([0, 1, 3, 10, 40, rng.randint(0, 60)])
    n = rng.randint(0, 14)
    t = rng.randint(0, 5)
    arr = []
    for j in range(n):
        t += rng.choice([0, 0, 1, 2, 5, 20])
        arr.append((t, "d%d" % j, rng.choice([0, 10, 55, 90, 100, rng.randint(0, 100)])))
    if n >= 2 and rng.random() < 0.04 and arr[0][0] != arr[-1][0]:
        arr[0], arr[-1] = arr[-1], arr[0]
    return (levels, threshold, patience, arr)
