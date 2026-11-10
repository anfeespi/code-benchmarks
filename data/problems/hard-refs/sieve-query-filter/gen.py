N = 1500

FIELDS = ["a", "b", "c.d", "name", "x_1"]
STRS = ['"x"', '"y"', '""', '"a\\"b"', '"\\\\"', '"10"']


def lit(rng):
    return str(rng.choice([-2, -1, 0, 1, 2, 3, 10])) if rng.random() < 0.6 else rng.choice(STRS)


def q(rng, d):
    r = rng.random()
    if d <= 0 or r < 0.35:
        k = rng.random()
        f = rng.choice(FIELDS)
        if k < 0.6:
            return "%s %s %s" % (f, rng.choice(["=", "!=", "<", "<=", ">", ">="]), lit(rng))
        if k < 0.85:
            return "%s in [%s]" % (f, ", ".join(lit(rng) for _ in range(rng.randint(1, 3))))
        return "has " + f
    if r < 0.5:
        return "not " + q(rng, d - 1)
    if r < 0.65:
        return "(" + q(rng, d - 1) + ")"
    return q(rng, d - 1) + rng.choice([" and ", " or "]) + q(rng, d - 1)


def rec(rng):
    out = {}
    for f in FIELDS:
        if rng.random() < 0.6:
            out[f] = rng.choice([-1, 0, 1, 2, 10]) if rng.random() < 0.6 else rng.choice(["x", "y", "", 'a"b', "\\", "10"])
    return out


def gen(rng):
    s = q(rng, rng.randint(0, 4))
    for _ in range(rng.choice([0, 0, 0, 1, 1, 2])):
        p = rng.randint(0, len(s))
        m = rng.random()
        if m < 0.5:
            s = s[:p] + rng.choice(["(", ")", "[", "]", ",", "!", "-", '"', "\\", "#", " and", "or ", "not", "=", "in", "has", "1", "x"]) + s[p:]
        elif m < 0.8 and s:
            s = s[:p] + s[p + 1:]
        else:
            s = s[:p]
    return (s, [rec(rng) for _ in range(rng.randint(0, 6))])
