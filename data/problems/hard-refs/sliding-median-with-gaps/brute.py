def window_medians(readings, k):
    if not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive int")
    out = []
    for i in range(len(readings)):
        vals = sorted(v for v in readings[max(0, i - k + 1):i + 1] if v is not None)
        out.append(vals[(len(vals) - 1) // 2] if vals else None)
    return out
