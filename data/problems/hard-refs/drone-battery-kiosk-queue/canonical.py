from collections import deque


def run_kiosk(levels, threshold, patience, arrivals):
    for a, b in zip(arrivals, arrivals[1:]):
        if b[0] < a[0]:
            raise ValueError("arrivals out of order")
    slots = [[c, 0] for c in levels]  # [charge when placed, time placed]
    out = []
    queue = deque()  # (drone, arrival time)
    n = len(arrivals)
    i = 0

    def best(t):
        bk, bc = -1, -1
        for k, (c0, t0) in enumerate(slots):
            c = c0 + t - t0
            if c > 100:
                c = 100
            if c >= threshold and c > bc:
                bk, bc = k, c
        return bk

    def swap(drone, charge, t, k):
        slots[k] = [charge, t]
        out.append((drone, "SWAP", t, k))

    charge_of = {}
    while i < n or queue:
        cands = []
        if i < n:
            cands.append(arrivals[i][0])
        if queue:
            cands.append(queue[0][1] + patience)
            cands.append(min(t0 + max(0, threshold - c0) for c0, t0 in slots))
        t = min(cands)
        while queue:
            k = best(t)
            if k < 0:
                break
            d, _ = queue.popleft()
            swap(d, charge_of.pop(d), t, k)
        while i < n and arrivals[i][0] == t:
            _, d, c = arrivals[i]
            i += 1
            k = best(t) if not queue else -1
            if k >= 0:
                swap(d, c, t, k)
            else:
                charge_of[d] = c
                queue.append((d, t))
        while queue and queue[0][1] + patience <= t:
            d, _ = queue.popleft()
            charge_of.pop(d)
            out.append((d, "LEFT", t))
    return out
