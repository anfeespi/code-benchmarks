N = 1500

NAMES = ["a", "b", "zz", "x_1", "_t", "q9"]


def expr(rng, d):
    if d <= 0 or rng.random() < 0.25:
        r = rng.random()
        if r < 0.55:
            return str(rng.choice([0, 1, 2, 3, 5, 7, 12, 300, rng.randint(0, 99)]))
        if r < 0.9:
            return rng.choice(NAMES)
        return "(" + expr(rng, d - 1) + ")"
    k = rng.random()
    if k < 0.12:
        return "-" + expr(rng, d - 1)
    if k < 0.2:
        return expr(rng, d - 1) + " ? " + expr(rng, d - 1) + " : " + expr(rng, d - 1)
    if k < 0.3:
        return "(" + expr(rng, d - 1) + ")"
    if rng.random() < 0.15:
        op = rng.choice(["<", "<=", ">", ">=", "==", "!="])
    else:
        op = rng.choice(["+", "-", "*", "/", "/", "%", "%", "^", "^"])
    sp = rng.choice(["", " "])
    return expr(rng, d - 1) + sp + op + sp + expr(rng, d - 1)


def gen(rng):
    s = expr(rng, rng.randint(0, 5))
    for _ in range(rng.choice([0, 0, 0, 1, 1, 2])):
        m = rng.random()
        p = rng.randint(0, len(s))
        if m < 0.45:
            s = s[:p] + rng.choice(list("+-*/%^()?:<>=! a1#XÉ.") + ["==", "<=", "!"]) + s[p:]
        elif m < 0.8 and s:
            s = s[:p] + s[p + 1:]
        else:
            s = s[:p]
    env = {n: rng.choice([0, 1, 2, -3, 4, 10]) for n in NAMES if rng.random() < 0.75}
    return (s, env)
