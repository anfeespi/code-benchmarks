N = 1500

SEGS = ["a", "b", "a", "*", "**", "**", "x.y"]
PSEGS = ["a", "b", "a", "x.y"]
PRINCIPALS = ["*", "user:ann", "user:bob", "group:eng", "group:ops"]
ACTIONS = ["*", "read", "write", "read,write", "write,read,read"]
BAD_RULES = ["ALLOW * read", "ALLOW * read /a extra", "allow * read /a", "PERMIT * read /a", "ALLOW user:Ann read /a",
             "ALLOW user: read /a", "ALLOW role:x read /a", "ALLOW ** read /a", "ALLOW * read, /a", "ALLOW * Read /a",
             "ALLOW * read,* /a", "ALLOW * read a", "ALLOW * read /a/", "ALLOW * read //a", "ALLOW * read /a/***",
             "ALLOW * read /A", "", 7, None, "DENY group:eng-x * /", "DENY * * /a b"]
BAD_REQ = [("ann", ["eng"], "read"), ["ann", ["eng"], "read", "/a"], ("Ann", [], "read", "/a"), ("", [], "read", "/a"),
           ("ann", ("eng",), "read", "/a"), ("ann", ["eng", "Ops"], "read", "/a"), ("ann", [None], "read", "/a"),
           ("ann", [], "", "/a"), ("ann", [], "read,write", "/a"), ("ann", [], "read", "a"),
           ("ann", [], "read", "/a/*"), ("ann", [], "read", "/a/"), ("ann", [], "read", None), (None, None, None, None)]


def _rule(rng):
    segs = [rng.choice(SEGS) for _ in range(rng.randint(0, 3))]
    res = "/" + "/".join(segs)
    sep = rng.choice([" ", "  ", "\t", " \n "])
    s = sep.join([rng.choice(["ALLOW", "DENY"]), rng.choice(PRINCIPALS), rng.choice(ACTIONS), res])
    if rng.random() < 0.1:
        s = "  " + s + " "
    return s


def _req(rng):
    path = "/" + "/".join(rng.choice(PSEGS) for _ in range(rng.randint(0, 3)))
    groups = rng.sample(["eng", "ops", "qa"], rng.randint(0, 2))
    return (rng.choice(["ann", "bob"]), groups, rng.choice(["read", "write", "exec"]), path)


def gen(rng):
    rules = [_rule(rng) for _ in range(rng.randint(0, 12))]
    reqs = [_req(rng) for _ in range(rng.randint(0, 6))]
    r = rng.random()
    if r < 0.1:
        rules.insert(rng.randint(0, len(rules)), rng.choice(BAD_RULES))
        if rng.random() < 0.3:
            reqs.insert(rng.randint(0, len(reqs)), rng.choice(BAD_REQ))
    elif r < 0.2:
        reqs.insert(rng.randint(0, len(reqs)), rng.choice(BAD_REQ))
    elif r < 0.22:
        return (tuple(rules), reqs)
    elif r < 0.24:
        return (rules, tuple(reqs))
    return (rules, reqs)
