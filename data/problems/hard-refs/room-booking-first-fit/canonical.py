from bisect import bisect_left, bisect_right


def run_ops(ops):
    slots = sorted({(op[1], op[2]) for op in ops if op[0] == "book" and op[1] < op[2]})
    sid = {p: i for i, p in enumerate(slots)}
    m = max(len(slots), 1)
    size = 1
    while size < m:
        size *= 2
    INF = float("inf")
    FS = [INF] * (2 * size)   # first active start in node
    LE = [-INF] * (2 * size)  # last active end in node
    MG = [-1] * (2 * size)    # max gap between consecutive actives inside node
    fen = [0] * (m + 1)       # Fenwick of active lengths by slot

    def fen_add(i, d):
        i += 1
        while i <= m:
            fen[i] += d
            i += i & -i

    def fen_sum(i):  # slots [0, i)
        s = 0
        while i > 0:
            s += fen[i]
            i -= i & -i
        return s

    def set_slot(i, on):
        s, e = slots[i]
        n = size + i
        FS[n], LE[n], MG[n] = (s, e, -1) if on else (INF, -INF, -1)
        fen_add(i, (e - s) if on else -(e - s))
        n >>= 1
        while n:
            l, r = 2 * n, 2 * n + 1
            if FS[l] == INF:
                FS[n], LE[n], MG[n] = FS[r], LE[r], MG[r]
            elif FS[r] == INF:
                FS[n], LE[n], MG[n] = FS[l], LE[l], MG[l]
            else:
                FS[n], LE[n] = FS[l], LE[r]
                g = FS[r] - LE[l]
                MG[n] = max(MG[l], MG[r], g)
            n >>= 1

    def search(node, nl, nr, lo, d, prev):
        # first gap >= d scanning active slots with index >= lo, previous end `prev`
        if nr < lo or FS[node] == INF:
            return None, prev
        if lo <= nl:
            if FS[node] - prev >= d:
                return prev, prev
            if MG[node] < d:
                return None, LE[node]
        mid = (nl + nr) // 2
        res, prev = search(2 * node, nl, mid, lo, d, prev)
        if res is not None:
            return res, prev
        return search(2 * node + 1, mid + 1, nr, lo, d, prev)

    act_s, act_e = [], []
    out = []
    for op in ops:
        name = op[0]
        if name == "book":
            _, s, e = op
            if s >= e:
                out.append("INVALID")
                continue
            i = bisect_left(act_s, e)
            if i > 0 and act_e[i - 1] > s:
                out.append("CONFLICT")
                continue
            act_s.insert(i, s)
            act_e.insert(i, e)
            set_slot(sid[(s, e)], True)
            out.append(True)
        elif name == "cancel":
            s = op[1]
            i = bisect_left(act_s, s)
            if i < len(act_s) and act_s[i] == s:
                e = act_e[i]
                del act_s[i], act_e[i]
                set_slot(sid[(s, e)], False)
                out.append(e - s)
            else:
                out.append(0)
        elif name == "first_fit":
            _, t, d = op
            k = bisect_right(act_s, t) - 1
            x = act_e[k] if k >= 0 and act_e[k] > t else t
            nxt = k + 1
            if nxt == len(act_s) or act_s[nxt] - x >= d:
                out.append(x)
                continue
            res, last = search(1, 0, size - 1, sid[(act_s[nxt], act_e[nxt])] + 1, d, act_e[nxt])
            out.append(res if res is not None else last)
        elif name == "free_between":
            _, a, b = op
            if a >= b:
                out.append(0)
                continue
            busy = 0
            k = bisect_left(act_s, a) - 1
            if k >= 0 and act_e[k] > a:
                busy += min(act_e[k], b) - a
            i0, i1 = bisect_left(act_s, a), bisect_left(act_s, b)
            if i0 < i1:
                busy += fen_sum(bisect_left(slots, (b,))) - fen_sum(bisect_left(slots, (a,)))
                busy -= max(0, act_e[i1 - 1] - b)
            out.append(b - a - busy)
    return out
