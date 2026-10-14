from itertools import combinations


def budget_purchases(prices, queries):
    # literal definition: largest subset size whose cheapest-possible total fits, and that total
    out = []
    for l, r, budget in queries:
        window = prices[l:r + 1]
        best = (0, 0)
        for k in range(len(window), 0, -1):
            cheapest = min(sum(c) for c in combinations(window, k))
            if cheapest <= budget:
                best = (k, cheapest)
                break
        out.append(best)
    return out
