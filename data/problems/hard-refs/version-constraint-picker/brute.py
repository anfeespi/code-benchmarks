import re

N = r"(?:0|[1-9][0-9]*)"
VER = re.compile(rf"({N})\.({N})\.({N})(?:~rc([1-9][0-9]*))?")
CMP = re.compile(rf"(>=|<=|!=|>|<|=)?({N}\.{N}\.{N}(?:~rc[1-9][0-9]*)?)")
WILD = re.compile(rf"({N})(?:\.({N}))?\.\*")
TRAIN = re.compile(rf"@({N})\.({N})")


def _key(s):
    m = VER.fullmatch(s) if type(s) is str else None
    if not m:
        return None
    x, y, z, rc = m.groups()
    return (int(x), int(y), int(z), 1 if rc is None else 0, 0 if rc is None else int(rc))


def _parse_clause(t):
    if t == "*":
        return ("any",)
    m = TRAIN.fullmatch(t)
    if m:
        return ("train", int(m.group(1)), int(m.group(2)))
    m = WILD.fullmatch(t)
    if m:
        return ("wild", int(m.group(1)), None if m.group(2) is None else int(m.group(2)))
    m = CMP.fullmatch(t)
    if m:
        return ("cmp", m.group(1) or "=", _key(m.group(2)))
    return None


def _holds(c, k):
    if c[0] == "any":
        return True
    if c[0] == "train":
        return k[0] == c[1] and k[1] >= c[2]
    if c[0] == "wild":
        return k[0] == c[1] and (c[2] is None or k[1] == c[2])
    op, v = c[1], c[2]
    if op == "=":
        return k == v
    if op == "!=":
        return k != v
    if op == ">":
        return k > v
    if op == "<":
        return k < v
    if op == ">=":
        return k >= v
    return k <= v


def pick_version(available, constraint):
    if type(available) is not list:
        raise TypeError("available must be a list")
    for i in range(len(available)):
        if _key(available[i]) is None:
            raise ValueError(f"invalid version at index {i}: {available[i]!r}")
    if type(constraint) is not str:
        raise TypeError("constraint must be a str")
    if re.fullmatch(r" *", constraint):
        raise ValueError("empty constraint")
    alts = []
    for ai, raw in enumerate(constraint.split("|")):
        body = raw.strip(" ")
        allow_rc = False
        if body[:1] == "?":
            allow_rc = True
            body = body[1:].strip(" ")
        if body == "":
            raise ValueError(f"alternative {ai + 1} is empty")
        clauses = []
        for ci, craw in enumerate(body.split(",")):
            t = craw.strip(" ")
            c = _parse_clause(t)
            if c is None:
                raise ValueError(f"alternative {ai + 1}, clause {ci + 1}: invalid clause {t!r}")
            clauses.append(c)
        alts.append((allow_rc, clauses))
    matching = []
    for s in available:
        k = _key(s)
        ok = any((k[3] == 1 or rc) and all(_holds(c, k) for c in cl) for rc, cl in alts)
        if ok:
            matching.append((k, s))
    if not matching:
        return None
    matching.sort(key=lambda t: t[0])
    return matching[-1][1]
