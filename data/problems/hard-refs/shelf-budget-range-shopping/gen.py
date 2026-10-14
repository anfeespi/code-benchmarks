N = 600


def gen(rng):
    n = rng.randint(1, 10)
    hi = rng.choice([1, 3, 10, 1000])
    prices = [rng.randint(1, hi) for _ in range(n)]
    queries = []
    for _ in range(rng.randint(0, 8)):
        l = rng.randint(0, n - 1)
        r = rng.randint(l, n - 1)
        total = sum(prices[l:r + 1])
        budget = rng.choice([0, rng.randint(0, total + 2), total, total - 1 if total else 0, total + 5])
        queries.append((l, r, max(0, budget)))
    return (prices, queries)
