from fractions import Fraction
import math


def _dec(s, maxfrac):
    if type(s) is not str or not s or s.count(".") > 1:
        raise ValueError("invalid input")
    ip, _, fp = s.partition(".")
    if "." in s and not fp:
        raise ValueError("invalid input")
    if not ip or len(fp) > maxfrac:
        raise ValueError("invalid input")
    for ch in ip + fp:
        if ch not in "0123456789":
            raise ValueError("invalid input")
    return Fraction(int(ip + fp), 10 ** len(fp))


def _money(fr):
    c = fr * 100
    assert c.denominator == 1
    c = c.numerator
    return str(c // 100) + "." + str(c % 100).zfill(2)


def amortize(principal, annual_rate_pct, months):
    P = _dec(principal, 2)
    R = _dec(annual_rate_pct, 6)
    if type(months) is not int or months < 1 or months > 1200 or P == 0 or R > 100:
        raise ValueError("invalid input")
    m = R / 100 / 12
    if m == 0:
        A = P / months
    else:
        A = P * m / (1 - (1 + m) ** (-months))
    pay = Fraction(math.ceil(A * 100), 100)
    bal = P
    out = []
    for t in range(1, months + 1):
        exact = bal * m * 100
        fl = math.floor(exact)
        diff = exact - fl
        if diff > Fraction(1, 2) or (diff == Fraction(1, 2) and fl % 2 == 1):
            fl += 1
        interest = Fraction(fl, 100)
        if t == months or bal + interest <= pay:
            out.append((_money(bal + interest), _money(interest), "0.00"))
            return out
        bal = bal - (pay - interest)
        out.append((_money(pay), _money(interest), _money(bal)))
    return out
