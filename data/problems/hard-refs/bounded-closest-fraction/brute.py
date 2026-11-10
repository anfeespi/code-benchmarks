from fractions import Fraction
from decimal import Decimal, InvalidOperation
import math

_OK = set("0123456789+-.eE")


def _parse(s):
    if type(s) is not str or not s or not set(s) <= _OK or "_" in s:
        raise ValueError("invalid input")
    # Decimal accepts a superset (e.g. "inf", "nan", spaces, underscores) which the charset check excluded,
    # but it also accepts forms like "1e5" and ".5", "5." just like the grammar.
    body = s[1:] if s[0] in "+-" else s
    if not body or body[0] in "eE" or body.startswith(".e") or body.startswith(".E") or body == ".":
        raise ValueError("invalid input")
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ValueError("invalid input")
    if not d.is_finite():
        raise ValueError("invalid input")
    return Fraction(d)


def closest_fraction(x, max_num, max_den):
    if type(max_num) is not int or type(max_den) is not int or max_num < 0 or max_den < 1:
        raise ValueError("invalid input")
    v = _parse(x)
    best = None
    for b in range(1, max_den + 1):
        f = math.floor(v * b)
        for a in (f, f + 1):
            a = max(-max_num, min(max_num, a))
            c = Fraction(a, b)
            key = (abs(c - v), c.denominator, abs(c.numerator))
            if best is None or key < best[0]:
                best = (key, c)
    c = best[1]
    return "%d/%d" % (c.numerator, c.denominator)
