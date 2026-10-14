def leaderboard_ranks(submissions):
    n = len(submissions)
    if n == 0:
        return []
    # every possible leaderboard key is (-score, index) of some submission; rank them offline
    order = sorted(range(n), key=lambda i: (-submissions[i][1], i))
    pos = [0] * n
    for r, i in enumerate(order):
        pos[i] = r + 1  # 1-based Fenwick position
    tree = [0] * (n + 1)

    def add(i, d):
        while i <= n:
            tree[i] += d
            i += i & -i

    def prefix(i):
        s = 0
        while i > 0:
            s += tree[i]
            i -= i & -i
        return s

    best = {}  # player -> (score, submission index that set it)
    out = []
    for i, (player, score) in enumerate(submissions):
        cur = best.get(player)
        if cur is None or score > cur[0]:
            if cur is not None:
                add(pos[cur[1]], -1)
            cur = (score, i)
            best[player] = cur
            add(pos[i], 1)
        out.append(prefix(pos[cur[1]]))
    return out
