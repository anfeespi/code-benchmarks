from itertools import product


def best_context(messages, budget, max_gap, bonus):
    if budget < 0 or max_gap < 0:
        raise ValueError("budget and max_gap must be >= 0")
    n = len(messages)
    best = None
    for keep in product((False, True), repeat=n):
        if any(m[2] and not k for m, k in zip(messages, keep)):
            continue
        if sum(m[0] for m, k in zip(messages, keep) if k) > budget:
            continue
        run, ok = 0, True
        for k in keep:
            run = 0 if k else run + 1
            if run > max_gap:
                ok = False
                break
        if not ok:
            continue
        score = sum(m[1] for m, k in zip(messages, keep) if k)
        score += bonus * sum(1 for i in range(n - 1) if keep[i] and keep[i + 1])
        if best is None or score > best:
            best = score
    return best
