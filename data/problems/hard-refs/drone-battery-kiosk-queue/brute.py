# Independent reference: integer clock, every slot charged one unit per tick.
def run_kiosk(levels, threshold, patience, arrivals):
    for x, y in zip(arrivals, arrivals[1:]):
        if y[0] < x[0]:
            raise ValueError("arrivals out of order")
    charge = list(levels)
    waiting = []  # list of [drone, arrival, charge]
    rec = []
    pending = list(arrivals)
    t = 0
    while pending or waiting:
        if t > 0:
            charge = [min(100, c + 1) for c in charge]

        def pick():
            ok = [(c, -k) for k, c in enumerate(charge) if c >= threshold]
            if not ok:
                return None
            c, nk = max(ok)
            return -nk

        while waiting:
            k = pick()
            if k is None:
                break
            d, _, c = waiting.pop(0)
            charge[k] = c
            rec.append((d, "SWAP", t, k))
        while pending and pending[0][0] == t:
            _, d, c = pending.pop(0)
            k = pick() if not waiting else None
            if k is None:
                waiting.append([d, t, c])
            else:
                charge[k] = c
                rec.append((d, "SWAP", t, k))
        keep = []
        for w in waiting:
            if w[1] + patience <= t:
                rec.append((w[0], "LEFT", t))
            else:
                keep.append(w)
        waiting = keep
        t += 1
    return rec
