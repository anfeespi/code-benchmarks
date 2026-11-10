import sys


def fence_report(colors, operations):
    n = len(colors)
    out = []
    if n == 0:
        return out
    size = 4 * n
    LC = [0] * size; RC = [0] * size; RUNS = [0] * size
    BEST = [0] * size; PRE = [0] * size; SUF = [0] * size
    LZ = [None] * size

    def pull(x, ln, rn):
        a, b = 2 * x, 2 * x + 1
        join = RC[a] == LC[b]
        LC[x] = LC[a]; RC[x] = RC[b]
        RUNS[x] = RUNS[a] + RUNS[b] - join
        best = BEST[a] if BEST[a] > BEST[b] else BEST[b]
        if join and SUF[a] + PRE[b] > best:
            best = SUF[a] + PRE[b]
        BEST[x] = best
        PRE[x] = PRE[a] + PRE[b] if (join and PRE[a] == ln) else PRE[a]
        SUF[x] = SUF[b] + SUF[a] if (join and SUF[b] == rn) else SUF[b]

    def setall(x, length, c):
        LC[x] = RC[x] = c
        RUNS[x] = 1
        BEST[x] = PRE[x] = SUF[x] = length
        LZ[x] = c

    def build(x, lo, hi):
        if lo == hi:
            LC[x] = RC[x] = colors[lo]
            RUNS[x] = BEST[x] = PRE[x] = SUF[x] = 1
            return
        mid = (lo + hi) >> 1
        build(2 * x, lo, mid)
        build(2 * x + 1, mid + 1, hi)
        pull(x, mid - lo + 1, hi - mid)

    def paint(x, lo, hi, l, r, c):
        if l <= lo and hi <= r:
            setall(x, hi - lo + 1, c)
            return
        mid = (lo + hi) >> 1
        z = LZ[x]
        if z is not None:
            setall(2 * x, mid - lo + 1, z)
            setall(2 * x + 1, hi - mid, z)
            LZ[x] = None
        if l <= mid:
            paint(2 * x, lo, mid, l, r, c)
        if r > mid:
            paint(2 * x + 1, mid + 1, hi, l, r, c)
        pull(x, mid - lo + 1, hi - mid)

    def collect(x, lo, hi, l, r, acc):
        if l <= lo and hi <= r:
            acc.append((x, hi - lo + 1))
            return
        mid = (lo + hi) >> 1
        z = LZ[x]
        if z is not None:
            setall(2 * x, mid - lo + 1, z)
            setall(2 * x + 1, hi - mid, z)
            LZ[x] = None
        if l <= mid:
            collect(2 * x, lo, mid, l, r, acc)
        if r > mid:
            collect(2 * x + 1, mid + 1, hi, l, r, acc)

    old = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old, 10000))
    try:
        build(1, 0, n - 1)
        for op in operations:
            if op[0] == "paint":
                _, l, r, c = op
                paint(1, 0, n - 1, l, r, c)
            else:
                _, l, r = op
                acc = []
                collect(1, 0, n - 1, l, r, acc)
                x, length = acc[0]
                rc, runs, best, suf = RC[x], RUNS[x], BEST[x], SUF[x]
                for x, length in acc[1:]:
                    join = rc == LC[x]
                    runs += RUNS[x] - join
                    if BEST[x] > best:
                        best = BEST[x]
                    if join and suf + PRE[x] > best:
                        best = suf + PRE[x]
                    suf = suf + length if (join and PRE[x] == length) else SUF[x]
                    rc = RC[x]
                out.append((runs, best))
    finally:
        sys.setrecursionlimit(old)
    return out
