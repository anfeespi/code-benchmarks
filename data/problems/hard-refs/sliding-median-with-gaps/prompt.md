This function computes a rolling median over a sensor stream in O(log k) per reading
using two heaps with lazy deletion. It works on simple hand-made streams, but on
production streams its output drifts from a straightforward recomputation, and some
streams crash with IndexError. Find and fix the bug(s),
returning a corrected version with the exact same function name and signature
(`window_medians(readings, k)`). Keep it efficient.

Current (buggy) implementation:

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

Contract:
- `readings` is a list whose elements are ints or None (None = the sensor reported
  nothing for that tick). It must not be modified.
- `k` must be an int >= 1, otherwise raise ValueError (also for an empty `readings`).
- For each index i (0-based), the WINDOW of i is the slice
  readings[max(0, i - k + 1) : i + 1], i.e. the last k ticks ending at i (fewer at the
  start of the stream). None entries occupy a tick in the window but are not values.
- Let V be the sorted list of the int values (non-None) in the window of i. Element i of
  the result is V[(len(V) - 1) // 2] (the LOWER median for even counts), or None if V is
  empty. Duplicate values count separately.
- Return the list of these len(readings) results ([] for an empty stream).

Performance: streams of up to 200,000 readings with k up to 200,000 must be processed in
a few seconds.

Examples:
- window_medians([5, 1, 3, 3, 9], 3) == [5, 1, 3, 3, 3]
- window_medians([4, None, 2, None, None, 7], 2) == [4, 4, 2, 2, None, 7]
- window_medians([2, 2, 1, 2, 1, 1], 4) == [2, 2, 2, 2, 1, 1]
