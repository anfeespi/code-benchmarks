from bisect import bisect_left


def run_ops(ops):
    vals = sorted({op[1] for op in ops if op[0] == "add"})
    pos = {v: i + 1 for i, v in enumerate(vals)}
    n = len(vals)
    tree = [0] * (n + 1)
    top = 1
    while top * 2 <= n:
        top *= 2

    def fadd(i, d):
        while i <= n:
            tree[i] += d
            i += i & -i

    def prefix(i):
        s = 0
        while i > 0:
            s += tree[i]
            i -= i & -i
        return s

    def kth(k):  # smallest i with prefix(i) >= k
        i, step = 0, top
        while step:
            j = i + step
            if j <= n and tree[j] < k:
                i = j
                k -= tree[j]
            step >>= 1
        return vals[i]

    cnt = {}
    size = 0
    distinct = 0
    log = []          # undo log: (value, delta) of every effective change
    cp_pos = {}       # checkpoint id -> log length when it was taken
    valid = []        # valid checkpoint ids, increasing
    next_id = 1
    out = []

    def change(v, d):
        nonlocal size, distinct
        c = cnt.get(v, 0)
        if c == 0 and d > 0:
            distinct += 1
        elif c == 1 and d < 0:
            distinct -= 1
        cnt[v] = c + d
        size += d
        fadd(pos[v], d)

    for op in ops:
        name = op[0]
        if name == "add":
            change(op[1], 1)
            log.append((op[1], 1))
            out.append(size)
        elif name == "remove":
            x = op[1]
            if cnt.get(x, 0) > 0:
                change(x, -1)
                log.append((x, -1))
                out.append(True)
            else:
                out.append(False)
        elif name == "checkpoint":
            cp_pos[next_id] = len(log)
            valid.append(next_id)
            out.append(next_id)
            next_id += 1
        elif name == "rollback":
            c = op[1]
            k = bisect_left(valid, c)
            if k == len(valid) or valid[k] != c:
                out.append("BADCP")
                continue
            del valid[k + 1:]
            target = cp_pos[c]
            while len(log) > target:
                v, d = log.pop()
                change(v, -d)
            out.append(size)
        elif name == "median":
            out.append(kth((size + 1) // 2) if size else None)
        elif name == "count_less":
            out.append(prefix(bisect_left(vals, op[1])))
        elif name == "distinct":
            out.append(distinct)
    return out
