import re

_AMOUNT = re.compile(r"([0-9]+)(?:\.([0-9]{1,2}))?")
_RATE = re.compile(r"([0-9]+)(?:\.([0-9]{1,6}))?")


def _fmt(c):
    return "%d.%02d" % divmod(c, 100)


def _div_half_even(a, b):
    """round(a / b) with ties to even, a >= 0, b > 0."""
    q, r = divmod(a, b)
    if 2 * r > b or (2 * r == b and q & 1):
        q += 1
    return q


def amortize(principal, annual_rate_pct, months):
    if not isinstance(principal, str) or not isinstance(annual_rate_pct, str):
        raise ValueError("invalid input")
    mp = _AMOUNT.fullmatch(principal)
    mr = _RATE.fullmatch(annual_rate_pct)
    if not mp or not mr or type(months) is not int or not (1 <= months <= 1200):
        raise ValueError("invalid input")
    bal = int(mp.group(1)) * 100 + int((mp.group(2) or "").ljust(2, "0"))
    rate_u = int(mr.group(1)) * 10 ** 6 + int((mr.group(2) or "").ljust(6, "0"))  # percent * 1e6
    if bal == 0 or rate_u > 100 * 10 ** 6:
        raise ValueError("invalid input")
    # monthly rate m = rate_u / (1200 * 10**6) = rn / rd
    rn, rd = rate_u, 1200 * 10 ** 6
    if rn == 0:
        pay = -(-bal // months)
    else:
        # A = bal * m / (1 - (1+m)^-n) = bal * rn * (rd+rn)^n / (rd * ((rd+rn)^n - rd^n))   [in cents]
        g = (rd + rn) ** months
        h = rd ** months
        num = bal * rn * g
        den = rd * (g - h)
        pay = -(-num // den)
    rows = []
    for t in range(1, months + 1):
        interest = _div_half_even(bal * rn, rd)
        if t == months or bal + interest <= pay:
            rows.append((_fmt(bal + interest), _fmt(interest), _fmt(0)))
            break
        bal -= pay - interest
        rows.append((_fmt(pay), _fmt(interest), _fmt(bal)))
    return rows
