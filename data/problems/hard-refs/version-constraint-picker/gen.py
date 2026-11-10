N = 1500

GOOD_V = ["0.0.0", "0.0.1", "0.1.0", "1.0.0", "1.0.0~rc1", "1.0.0~rc2", "1.0.0~rc10", "1.2.3", "1.2.10",
          "1.10.0", "1.10.0~rc1", "2.0.0", "2.0.0~rc1", "2.1.0", "10.0.0", "1.9.9"]
BAD_V = ["01.0.0", "1.0", "1.0.0.0", "v1.0.0", "1.0.0~rc0", "1.0.0~rc01", "1.0.0~beta1", "1.0.0~rc", " 1.0.0",
         "1.0.0 ", "1..0", "", None, 100, "1.0.0~RC1", "1.0.0-rc1", "１.0.0"]
CLAUSES = ["*", "1.0.0", "=1.0.0", "!=1.0.0", ">1.0.0", ">=1.0.0~rc1", "<2.0.0", "<=1.10.0", "1.*", "2.*",
           "1.0.*", "1.10.*", "@1.2", "@0.0", "@1.10", "!=1.0.0~rc2", "<1.0.0", ">=0.1.0", "=1.0.0~rc10",
           "0.*", "10.*", "1.9.9", ">2.0.0~rc1"]
BAD_CLAUSES = ["", "==1.0.0", "<1.*", "@1", "@1.2.3", "1.2.3.*", "1.*.*", ".*", "> 1.0.0", ">=01.0.0", "1.0",
               "?1.0.0", "x", "*.*", "=*", "@01.2", "1.0.0~rc0", "\t1.0.0", "1.2.*,"]


def _alt(rng):
    cl = [rng.choice(CLAUSES) for _ in range(rng.randint(1, 3))]
    sep = rng.choice([",", ", ", " , "])
    s = sep.join(cl)
    if rng.random() < 0.4:
        s = rng.choice(["?", "? ", " ?"]) + s
    if rng.random() < 0.3:
        s = " " + s + " "
    return s


def gen(rng):
    avail = [rng.choice(GOOD_V) for _ in range(rng.randint(0, 6))]
    cons = "|".join(_alt(rng) for _ in range(rng.randint(1, 3)))
    r = rng.random()
    if r < 0.08:
        avail.insert(rng.randint(0, len(avail)), rng.choice(BAD_V))
    elif r < 0.10:
        avail = tuple(avail)
    elif r < 0.12:
        cons = rng.choice([None, 5, b"1.*"])
    elif r < 0.16:
        cons = rng.choice(["", "   ", "|", "1.* |", " | 1.*", "?", "1.*| ? |2.*", "\t"])
    elif r < 0.30:
        parts = cons.split("|")
        k = rng.randrange(len(parts))
        sub = parts[k].split(",")
        sub[rng.randrange(len(sub))] = rng.choice(BAD_CLAUSES)
        parts[k] = ",".join(sub)
        cons = "|".join(parts)
    return (avail, cons)
