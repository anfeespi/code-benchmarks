import heapq
from collections import defaultdict


def window_medians(readings, k):
    if not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive int")

    low = []    # max-heap via negation: the smaller half, its top is the median
    high = []   # min-heap: the larger half
    delayed = defaultdict(int)  # value -> pending lazy deletions
    sizes = {"low": 0, "high": 0}  # live (not yet deleted) element counts
    out = []

    def prune(heap, sign):
        # drop deleted values sitting on top of a heap
        while heap and delayed[sign * heap[0]]:
            delayed[sign * heap[0]] -= 1
            heapq.heappop(heap)

    def rebalance():
        # invariant: sizes["low"] == sizes["high"] or sizes["low"] == sizes["high"] + 1
        if sizes["low"] > sizes["high"] + 1:
            heapq.heappush(high, -heapq.heappop(low))
            sizes["low"] -= 1
            sizes["high"] += 1
            prune(low, -1)
        elif sizes["low"] < sizes["high"]:
            heapq.heappush(low, -heapq.heappop(high))
            sizes["high"] -= 1
            sizes["low"] += 1

    def add(x):
        if not low or x <= -low[0]:
            heapq.heappush(low, -x)
            sizes["low"] += 1
        else:
            heapq.heappush(high, x)
            sizes["high"] += 1
        rebalance()

    def remove(x):
        delayed[x] += 1
        if x < -low[0]:
            sizes["low"] -= 1
            if x == -low[0]:
                prune(low, -1)
        else:
            sizes["high"] -= 1
            if x == high[0]:
                prune(high, 1)
        rebalance()

    for i, x in enumerate(readings):
        if x is None:
            out.append(-low[0] if sizes["low"] else None)
            continue
        add(x)
        if i >= k and readings[i - k] is not None:
            remove(readings[i - k])
        out.append(-low[0] if sizes["low"] else None)
    return out
