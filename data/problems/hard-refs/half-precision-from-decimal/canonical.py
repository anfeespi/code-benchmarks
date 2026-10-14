import re

_GRAMMAR = re.compile(r"([+-]?)([0-9]*)(?:\.([0-9]*))?(?:[eE]([+-]?[0-9]+))?")


def decimal_to_half_bits(s):
    if not isinstance(s, str):
        raise ValueError("invalid literal")
    m = _GRAMMAR.fullmatch(s)
    if not m:
        raise ValueError("invalid literal")
    sign, ip, fp, ex = m.group(1), m.group(2), m.group(3), m.group(4)
    fp = fp or ""
    if not ip and not fp:
        raise ValueError("invalid literal")
    neg = 0x8000 if sign == "-" else 0
    allds = ip + fp
    digits = allds.lstrip("0")
    if not digits:
        return neg
    # decimal exponent of the last digit of `allds`; absurd exponents are clamped (still decisive)
    if ex is None:
        e_in = 0
    else:
        mag = ex.lstrip("+-").lstrip("0") or "0"
        e_in = int(mag) if len(mag) <= 15 else 10 ** 15
        if ex.startswith("-"):
            e_in = -e_in
    nd = len(digits)
    e10 = e_in - len(fp)
    # only ~30 significant digits can matter: keep 40 plus a sticky digit for anything nonzero beyond
    if nd > 40:
        tail_nonzero = digits[40:].strip("0") != ""
        e10 += nd - 40
        digits = digits[:40]
        if tail_nonzero:
            digits += "1"
            e10 -= 1
        nd_eff = len(digits)
    else:
        nd_eff = nd
    mant = int(digits)
    # magnitude test uses the true digit count: value in [10**(nd-1+E), 10**(nd+E)), E = exponent of last digit
    nd, e10_true = nd, e10 + nd_eff - nd
    if nd - 1 + e10_true >= 5:      # >= 100000 > 65520 -> overflow
        return neg | 0x7C00
    if nd + e10_true <= -8:         # < 1e-8 < 2**-25 -> rounds to zero
        return neg
    if e10 >= 0:
        num, den = mant * 10 ** e10, 1
    else:
        num, den = mant, 10 ** (-e10)
    # e = floor(log2(num/den))
    e = num.bit_length() - den.bit_length()
    if (num << -e if e < 0 else num) < (den << e if e > 0 else den):
        e -= 1
    ee = max(e, -14)
    sh = 10 - ee                # scaled = num/den * 2**sh
    if sh >= 0:
        a, b = num << sh, den
    else:
        a, b = num, den << -sh
    n, r = divmod(a, b)
    if 2 * r > b or (2 * r == b and n & 1):
        n += 1
    if n == 2048:
        n = 1024
        ee += 1
    if ee > 15:
        return neg | 0x7C00
    if n < 1024:
        return neg | n
    return neg | ((ee + 15) << 10) | (n - 1024)
