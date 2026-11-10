from bisect import bisect_left, bisect_right


def run_ops(ops):
    # persistent segment tree over the offline-compressed set of keys that can ever be stored
    keys = sorted({op[2] for op in ops if op[0] in ("set", "del")})
    m = max(len(keys), 1)
    idx = {k: i for i, k in enumerate(keys)}
    L, R, C, S = [0], [0], [0], [0]  # node 0 is the shared empty node
    roots = [0]
    out = []

    def update(root, pos, present, value):
        # returns new root after setting leaf `pos`
        path = []
        node, lo, hi = root, 0, m - 1
        while lo < hi:
            mid = (lo + hi) >> 1
            path.append((node, pos <= mid))
            if pos <= mid:
                node, hi = L[node], mid
            else:
                node, lo = R[node], mid + 1
        L.append(0); R.append(0); C.append(1 if present else 0); S.append(value if present else 0)
        new = len(C) - 1
        for node, went_left in reversed(path):
            if went_left:
                l, r = new, R[node]
            else:
                l, r = L[node], new
            L.append(l); R.append(r); C.append(C[l] + C[r]); S.append(S[l] + S[r])
            new = len(C) - 1
        return new

    def leaf(root, pos):
        node, lo, hi = root, 0, m - 1
        while lo < hi and node:
            mid = (lo + hi) >> 1
            if pos <= mid:
                node, hi = L[node], mid
            else:
                node, lo = R[node], mid + 1
        return node

    def range_query(root, a, b):
        cnt = tot = 0
        stack = [(root, 0, m - 1)]
        while stack:
            node, lo, hi = stack.pop()
            if not node or hi < a or lo > b:
                continue
            if a <= lo and hi <= b:
                cnt += C[node]
                tot += S[node]
                continue
            mid = (lo + hi) >> 1
            stack.append((L[node], lo, mid))
            stack.append((R[node], mid + 1, hi))
        return cnt, tot

    def kth(root, k):
        node, lo, hi = root, 0, m - 1
        while lo < hi:
            mid = (lo + hi) >> 1
            if C[L[node]] >= k:
                node, hi = L[node], mid
            else:
                k -= C[L[node]]
                node, lo = R[node], mid + 1
        return keys[lo]

    def valid(v):
        return type(v) is int and 0 <= v < len(roots)

    for op in ops:
        name, v = op[0], op[1]
        if not valid(v):
            out.append("BADVER")
            continue
        root = roots[v]
        if name == "set":
            roots.append(update(root, idx[op[2]], True, op[3]))
            out.append(len(roots) - 1)
        elif name == "del":
            if op[2] not in idx or not C[leaf(root, idx[op[2]])]:
                out.append("NOKEY")
            else:
                roots.append(update(root, idx[op[2]], False, 0))
                out.append(len(roots) - 1)
        elif name == "get":
            k = op[2]
            if k in idx:
                nd = leaf(root, idx[k])
                out.append(S[nd] if C[nd] else None)
            else:
                out.append(None)
        elif name in ("count", "sum"):
            lo, hi = op[2], op[3]
            a, b = bisect_left(keys, lo), bisect_right(keys, hi) - 1
            cnt, tot = range_query(root, a, b) if a <= b else (0, 0)
            out.append(cnt if name == "count" else tot)
        elif name == "kth":
            k = op[2]
            out.append(kth(root, k) if 1 <= k <= C[root] else None)
    return out
