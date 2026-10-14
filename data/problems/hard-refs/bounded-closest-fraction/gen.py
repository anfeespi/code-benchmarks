N = 1500


def _dec(rng):
    ip = str(rng.randint(0, rng.choice([0, 1, 3, 12, 40])))
    fp = "".join(rng.choice("0123456789") for _ in range(rng.randint(0, 5)))
    if rng.random() < 0.3:
        fp = rng.choice(["5", "25", "75", "125", "375", "0625", "1", "2", "05", "45", "35"])
    s = ip + ("." + fp if fp else "")
    if rng.random() < 0.15:
        s = "." + fp if fp else ip
    if rng.random() < 0.2:
        # shift into exponent form without changing the value
        e = rng.randint(1, 3)
        s = s + "0" * 0
        if "." in s:
            a, b = s.split(".")
            s = (a or "0") + "." + b + "0" * e
            a, b = s.split(".")
            s = a + b[:e] + "." + b[e:] + "e-" + str(e)
        else:
            s = s + "0" * e + "E-" + str(e)
    return rng.choice(["", "", "-", "+"]) + s


def gen(rng):
    r = rng.random()
    if r < 0.03:
        return (rng.choice(["", ".", "e1", "1e", "1..2", "inf", "nan", " 1", "1_0", "--1", "0x1", ".e1", "1e+"]), 5, 5)
    if r < 0.05:
        return ("0.5", rng.choice([-1, 3]), rng.choice([0, -2]))
    if r < 0.07:
        return ("0.5", rng.choice([0, 1, 2]), 1)
    A = rng.choice([0, 1, 2, 3, 5, 7, 12, 30, 1000])
    B = rng.randint(1, 30)
    return (_dec(rng), A, B)
