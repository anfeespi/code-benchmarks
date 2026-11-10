_DIG = "0123456789abcdefghijklmnopqrstuvwxyz"


def _int_to_base(n, b):
    if n == 0:
        return "0"
    # chunked conversion: peel off as many digits per big division as fit comfortably
    k = 1
    while b ** (k + 1) < 2 ** 60:
        k += 1
    big = b ** k
    chunks = []
    while n:
        n, r = divmod(n, big)
        chunks.append(r)
    out = []
    for i, c in enumerate(reversed(chunks)):
        s = []
        for _ in range(k):
            c, d = divmod(c, b)
            s.append(_DIG[d])
        s = "".join(reversed(s))
        out.append(s.lstrip("0") or "0" if i == 0 else s)
    return "".join(out)


def format_base(p, q, base, k):
    if q == 0 or not (2 <= base <= 36) or k < 0:
        raise ValueError("bad arguments")
    neg = (p < 0) != (q < 0) and p != 0
    p, q = abs(p), abs(q)
    ip, r = divmod(p, q)
    # fractional digits by long division (remainder always < q, so each step is cheap)
    frac = []
    for _ in range(k):
        r *= base
        d, r = divmod(r, q)
        frac.append(d)
    # N = ip * base**k + frac digits; decide rounding from the final remainder
    twice = 2 * r
    up = twice > q
    if twice == q and r != 0:
        # tie: round to make N even. parity of N:
        if base % 2 == 0:
            par = frac[-1] % 2 if k else ip % 2
        else:
            par = (ip + sum(frac)) % 2  # base odd: base**j is odd, N = sum of digit*odd
        up = par == 1
    if up:
        i = k - 1
        while i >= 0 and frac[i] == base - 1:
            frac[i] = 0
            i -= 1
        if i >= 0:
            frac[i] += 1
        else:
            ip += 1
    while frac and frac[-1] == 0:
        frac.pop()
    if ip == 0 and not frac:
        return "0"
    s = _int_to_base(ip, base)
    if frac:
        s += "." + "".join(_DIG[d] for d in frac)
    return ("-" if neg else "") + s
