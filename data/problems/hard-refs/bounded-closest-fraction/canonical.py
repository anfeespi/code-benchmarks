import re
from math import gcd

_GRAMMAR = re.compile(r"([+-]?)([0-9]*)(?:\.([0-9]*))?(?:[eE]([+-]?[0-9]+))?")


def _parse(s):
    if not isinstance(s, str):
        raise ValueError("invalid input")
    m = _GRAMMAR.fullmatch(s)
    if not m or not (m.group(2) or m.group(3)):
        raise ValueError("invalid input")
    sign, ip, fp, ex = m.group(1), m.group(2), m.group(3) or "", m.group(4)
    num = int((ip + fp).lstrip("0") or "0")
    e = (int(ex) if ex else 0) - len(fp)
    den = 1
    if e >= 0:
        num *= 10 ** e
    else:
        den = 10 ** (-e)
    g = gcd(num, den)
    num, den = num // g, den // g
    return (-num if sign == "-" else num), den


def _best_nonneg(n, d, A, B):
    """Closest a/b to n/d >= 0 with 0 <= a <= A, 1 <= b <= B; returns list of the (one or two) nearest candidates."""
    if A == 0 or n == 0:
        return [(0, 1)]
    if n >= A * d:
        return [(A, 1)]
    # walk the continued fraction; (p0/q0, p1/q1) are consecutive convergents
    p0, q0, p1, q1 = 0, 1, 1, 0
    while True:
        a = n // d
        p2, q2 = p0 + a * p1, q0 + a * q1
        if q2 > B or p2 > A:
            break
        p0, q0, p1, q1 = p1, q1, p2, q2
        if n == a * d:
            return [(p1, q1)]
        n, d = d, n - a * d
    k = (B - q0) // q1
    if p1:
        k = min(k, (A - p0) // p1)
    return [(p0 + k * p1, q0 + k * q1), (p1, q1)]


def closest_fraction(x, max_num, max_den):
    if not isinstance(max_num, int) or not isinstance(max_den, int) or max_num < 0 or max_den < 1:
        raise ValueError("invalid input")
    n, d = _parse(x)
    neg = n < 0
    cands = _best_nonneg(abs(n), d, max_num, max_den)
    an = abs(n)

    # distances compare as |a/b - x| = |a*d - n*b| / (b*d); compare cross-multiplied
    best = None
    for a, b in cands:
        g = gcd(a, b)
        a, b = a // g, b // g
        if best is None:
            best = (a, b)
            continue
        ba, bb = best
        lhs = abs(a * d - an * b) * bb
        rhs = abs(ba * d - an * bb) * b
        if lhs < rhs or (lhs == rhs and (b < bb or (b == bb and a < ba))):
            best = (a, b)
    a, b = best
    if neg and a:
        a = -a
    return "%d/%d" % (a, b)
