from fractions import Fraction
import math

_DIG = "0123456789abcdefghijklmnopqrstuvwxyz"


def format_base(p, q, base, k):
    if q == 0 or not (2 <= base <= 36) or k < 0:
        raise ValueError("bad arguments")
    x = Fraction(p, q)
    scaled = abs(x) * base ** k
    lo = math.floor(scaled)
    cands = [lo, lo + 1]
    # nearest; tie -> even N
    n = min(cands, key=lambda c: (abs(c - scaled), c % 2))
    if n == 0:
        return "0"
    digs = []
    m = n
    while m:
        digs.append(_DIG[m % base])
        m //= base
    while len(digs) < k + 1:
        digs.append("0")
    s = "".join(reversed(digs))
    ip, fp = s[:len(s) - k], s[len(s) - k:]
    fp = fp.rstrip("0")
    out = ip + ("." + fp if fp else "")
    return ("-" if x < 0 else "") + out
