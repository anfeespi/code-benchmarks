import heapq


def fastest_delivery(n, roads, stations, capacity, swap_time, max_swaps, s, t):
    if s == t:
        return (0, 0)
    adj = [[] for _ in range(n)]
    for u, v, minutes, energy in roads:
        adj[u].append((v, minutes, energy))
    is_station = [False] * n
    for x in stations:
        is_station[x] = True
    C, K = capacity, max_swaps
    INF = float("inf")
    W = C + 1
    dist = [INF] * (n * W * (K + 1))

    def idx(v, c, k):
        return (v * W + c) * (K + 1) + k

    dist[idx(s, C, 0)] = 0
    pq = [(0, s, C, 0)]
    while pq:
        d, v, c, k = heapq.heappop(pq)
        if d > dist[idx(v, c, k)]:
            continue
        if is_station[v] and k < K:
            nd = d + swap_time
            j = idx(v, C, k + 1)
            if nd < dist[j]:
                dist[j] = nd
                heapq.heappush(pq, (nd, v, C, k + 1))
        for w, minutes, energy in adj[v]:
            if c < energy:
                continue
            nc = c - energy
            if nc > C:
                nc = C
            nd = d + minutes
            j = idx(w, nc, k)
            if nd < dist[j]:
                dist[j] = nd
                heapq.heappush(pq, (nd, w, nc, k))
    best = None
    for c in range(W):
        for k in range(K + 1):
            d = dist[idx(t, c, k)]
            if d < INF and (best is None or (d, k) < best):
                best = (d, k)
    return best
