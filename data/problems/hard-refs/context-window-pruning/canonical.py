def best_context(messages, budget, max_gap, bonus):
    if budget < 0 or max_gap < 0:
        raise ValueError("budget and max_gap must be >= 0")
    n = len(messages)
    B = budget
    NEG = float("-inf")
    start = [NEG] * (B + 1)
    start[0] = 0
    # dp[i][w]: best score with message i kept as the LAST kept one so far, total length w.
    # Index n is a virtual sentinel (length 0, value 0) that closes the trailing gap.
    dp = [None] * (n + 1)
    for i in range(n + 1):
        if i < n:
            L, v, _ = messages[i]
        else:
            L, v = 0, 0
        if L > B:
            continue
        best = [NEG] * (B + 1)
        j = i - 1
        while j >= -1 and i - j - 1 <= max_gap:
            src = start if j == -1 else dp[j]
            if src is not None:
                add = v + (bonus if (0 <= j == i - 1 and i < n) else 0)
                cand = [a + add for a in src[:B + 1 - L]]
                best[L:] = list(map(max, best[L:], cand))
            if j >= 0 and messages[j][2]:
                break  # cannot drop a pinned message, so no earlier predecessor is allowed
            j -= 1
        dp[i] = best
    if dp[n] is None:
        return None
    ans = max(dp[n])
    return None if ans == NEG else ans
