N = 600


def gen(rng):
    n = rng.randint(1, 10)
    # parents are NOT required to have smaller labels: build a tree on a random relabeling
    perm = list(range(1, n))
    rng.shuffle(perm)
    labels = [0] + perm
    parent = [-1] * n
    for i in range(1, n):
        parent[labels[i]] = labels[rng.randrange(i)]
    demand = [rng.choice([0, 1, 1, 2, 3, 5]) for _ in range(n)]
    cap = [rng.randint(0, 12) for _ in range(n)]
    cut_cost = [rng.choice([0, 1, 2, 5, 9]) for _ in range(n)]
    critical = [rng.random() < 0.15 for _ in range(n)]
    return (parent, demand, cap, cut_cost, critical, rng.randint(0, 20), rng.choice([0, 1, 2, 4]))
