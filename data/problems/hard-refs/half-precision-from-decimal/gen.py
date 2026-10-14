from fractions import Fraction

N = 800


def half_value(bits):
    e, f = bits >> 10, bits & 0x3FF
    if e == 0:
        return Fraction(f, 2 ** 24)
    return Fraction(1024 + f, 1024) * Fraction(2) ** (e - 15)


def exact_decimal(fr):
    """Exact decimal string of a dyadic rational >= 0."""
    k = 0
    while fr.denominator != 1:
        fr *= 10
        k += 1
    digits = str(fr.numerator).rjust(k + 1, "0")
    return digits[:len(digits) - k] + ("." + digits[len(digits) - k:] if k else "")


def _sci(dec, rng):
    """Optionally rewrite a plain decimal into an equivalent exponent form."""
    if rng.random() < 0.6 or "." not in dec:
        return dec
    ip, fp = dec.split(".")
    shift = rng.randint(1, 4)
    fp2 = fp + "0" * shift
    return ip + fp2[:shift] + "." + fp2[shift:] + rng.choice(["e-", "E-"]) + str(shift)


def gen(rng):
    kind = rng.randrange(9)
    sign = rng.choice(["", "", "-", "+"])
    if kind == 0:      # exactly representable
        return (sign + _sci(exact_decimal(half_value(rng.randrange(0x7C00))), rng),)
    if kind in (1, 2):  # exact midpoints between neighbours (ties), incl. subnormal and overflow boundary
        b = rng.choice([rng.randrange(0x7BFF), rng.randrange(0, 40), rng.randrange(0x7BC0, 0x7BFF), 0x3BFF, 0x3C00])
        lo = half_value(b)
        hi = half_value(b + 1) if b + 1 < 0x7C00 else Fraction(65536)
        mid = (lo + hi) / 2
        return (sign + _sci(exact_decimal(mid), rng),)
    if kind == 3:      # tiny nudge off a midpoint
        b = rng.randrange(0x7BFF)
        mid = (half_value(b) + half_value(b + 1)) / 2
        eps = Fraction(1, 2 ** rng.randint(30, 70)) * rng.choice([1, -1])
        return (sign + exact_decimal(mid + eps if mid + eps > 0 else mid),)
    if kind == 4:      # random short decimals
        ip = str(rng.randint(0, 70000)) if rng.random() < 0.7 else ""
        fp = "".join(rng.choice("0123456789") for _ in range(rng.randint(0, 8)))
        if not ip and not fp:
            fp = "5"
        s = ip + ("." + fp if fp or rng.random() < 0.3 else "")
        if s.endswith(".") and not ip:
            s = "0."
        return (sign + s,)
    if kind == 5:      # exponent forms spanning the range
        m = str(rng.randint(0, 99999))
        if rng.random() < 0.5:
            m = m[:1] + "." + m[1:]
        return (sign + m + rng.choice("eE") + rng.choice(["", "+", "-"]) + str(rng.randint(0, 12)),)
    if kind == 6:      # zeros
        return (sign + rng.choice(["0", "0.0", ".0", "0.", "000", "0e5", "0.000e-99"]),)
    if kind == 7:      # invalid literals
        return (rng.choice(["", ".", "+", "-", "e5", "1e", "1e+", "1.2.3", " 1", "1 ", "1_0", "inf", "nan", "0x10",
                            "--1", "+-1", "1e5.0", "١", "1,5", ".e1", "1d5"]),)
    # around the overflow threshold 65520 and the underflow threshold 2**-25
    base = rng.choice([Fraction(65520), Fraction(65504), Fraction(1, 2 ** 25), Fraction(1, 2 ** 24)])
    eps = Fraction(rng.randint(-3, 3), 2 ** rng.randint(30, 40))
    v = base + eps
    return (sign + exact_decimal(v),)
