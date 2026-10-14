N = 600


def gen(rng):
    r = rng.random()
    if r < 0.05:
        return (rng.choice(["", "0", "0.00", "1.234", "-5", "1,000", " 10", "1e3", ".5", "5.", "abc"]),
                rng.choice(["5", "5.", "-1", "100.0000001", "1.2345678", "x"]), rng.choice([0, 1, 12, 1201, -3]))
    if r < 0.08:
        return ("1000", "6", rng.choice([0, 1201, -1]))
    ip = str(rng.choice([rng.randint(1, 999), rng.randint(0, 99999), rng.randint(1, 10 ** rng.randint(1, 12))]))
    fp = rng.choice(["", "." + str(rng.randint(0, 9)), "." + str(rng.randint(0, 99)).zfill(2)])
    principal = ip + fp
    if principal.strip("0.") == "":
        principal = "1"
    rate = rng.choice([
        "0", "0.0", str(rng.randint(1, 30)), "%d.%d" % (rng.randint(0, 25), rng.randint(0, 9)),
        "%d.%s" % (rng.randint(0, 25), str(rng.randint(0, 999999)).zfill(rng.randint(1, 6))[:6]),
        "6", "12", "2.4", "100", "99.999999", "0.000001",
    ])
    months = rng.choice([1, 2, 3, rng.randint(1, 12), rng.randint(1, 60), rng.randint(1, 400)])
    return (principal, rate, months)
