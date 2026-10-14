from bisect import bisect_right
from itertools import accumulate


def budget_purchases(prices, queries):
    # correct but sorts every window: O(q * w log w)
    out = []
    for l, r, budget in queries:
        pref = list(accumulate(sorted(prices[l:r + 1])))
        k = bisect_right(pref, budget)
        out.append((k, pref[k - 1] if k else 0))
    return out
