from bisect import bisect_left
from fractions import Fraction

_VALUES = None


def _table():
    global _VALUES
    if _VALUES is None:
        vals = []
        for bits in range(0x7C00):
            e, f = bits >> 10, bits & 0x3FF
            if e == 0:
                v = Fraction(f, 2 ** 24)
            else:
                v = Fraction(1024 + f, 1024) * Fraction(2) ** (e - 15)
            vals.append(v)
        vals.append(Fraction(65536))  # infinity as the "next" value; its bit pattern 0x7C00 is even
        _VALUES = vals
    return _VALUES


def _parse(s):
    if type(s) is not str:
        raise ValueError("invalid literal")
    i, n = 0, len(s)
    neg = False
    if i < n and s[i] in "+-":
        neg = s[i] == "-"
        i += 1
    ip = ""
    while i < n and s[i] in "0123456789":
        ip += s[i]
        i += 1
    fp = ""
    if i < n and s[i] == ".":
        i += 1
        while i < n and s[i] in "0123456789":
            fp += s[i]
            i += 1
    if not ip and not fp:
        raise ValueError("invalid literal")
    exp = 0
    if i < n and s[i] in "eE":
        i += 1
        esign = 1
        if i < n and s[i] in "+-":
            esign = -1 if s[i] == "-" else 1
            i += 1
        ed = ""
        while i < n and s[i] in "0123456789":
            ed += s[i]
            i += 1
        if not ed:
            raise ValueError("invalid literal")
        exp = esign * int(ed)
    if i != n:
        raise ValueError("invalid literal")
    v = Fraction(int(ip + fp or "0"), 10 ** len(fp)) * Fraction(10) ** exp
    return neg, v


def decimal_to_half_bits(s):
    neg, v = _parse(s)
    sign = 0x8000 if neg else 0
    vals = _table()
    if v >= vals[-1]:
        return sign | 0x7C00
    j = bisect_left(vals, v)
    best = None
    for k in (j - 1, j):
        if 0 <= k < len(vals):
            key = (abs(vals[k] - v), k & 1)
            if best is None or key < best[0]:
                best = (key, k)
    return sign | best[1]
