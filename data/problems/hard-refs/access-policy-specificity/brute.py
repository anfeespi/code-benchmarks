import re

NAME = re.compile(r"[a-z0-9_]+")
ACT = re.compile(r"[a-z]+")
ACTS = re.compile(r"[a-z]+(,[a-z]+)*")
PRINC = re.compile(r"\*|user:[a-z0-9_]+|group:[a-z0-9_]+")
RES = re.compile(r"/|(/([a-z0-9._-]+|\*|\*\*))+")
PATH = re.compile(r"/|(/[a-z0-9._-]+)+")


def _ok(rx, s):
    return type(s) is str and rx.fullmatch(s) is not None


def _m(p, s):
    if not p:
        return not s
    if p[0] == "**":
        return any(_m(p[1:], s[k:]) for k in range(len(s) + 1))
    return bool(s) and (p[0] == "*" or p[0] == s[0]) and _m(p[1:], s[1:])


def _segs(path):
    return [] if path == "/" else path.split("/")[1:]


def evaluate_access(rules, requests):
    if type(rules) is not list:
        raise TypeError("rules must be a list")
    if type(requests) is not list:
        raise TypeError("requests must be a list")
    table = []
    for i, rule in enumerate(rules):
        if type(rule) is not str:
            raise TypeError(f"rule {i}: not a str")
        parts = rule.split()
        if len(parts) != 4:
            raise ValueError(f"rule {i}: expected 4 fields, got {len(parts)}")
        eff, pr, ac, rs = parts
        if eff != "ALLOW" and eff != "DENY":
            raise ValueError(f"rule {i}: bad effect {eff!r}")
        if not _ok(PRINC, pr):
            raise ValueError(f"rule {i}: bad principal {pr!r}")
        if ac != "*" and not _ok(ACTS, ac):
            raise ValueError(f"rule {i}: bad action {ac!r}")
        if not _ok(RES, rs):
            raise ValueError(f"rule {i}: bad resource {rs!r}")
        table.append((i, eff, pr, ac, rs))
    for j, rq in enumerate(requests):
        if type(rq) is not tuple or len(rq) != 4:
            raise TypeError(f"request {j}: expected 4-tuple")
        if not _ok(NAME, rq[0]):
            raise ValueError(f"request {j}: bad user {rq[0]!r}")
        if type(rq[1]) is not list or any(not _ok(NAME, g) for g in rq[1]):
            raise ValueError(f"request {j}: bad groups")
        if not _ok(ACT, rq[2]):
            raise ValueError(f"request {j}: bad action {rq[2]!r}")
        if not _ok(PATH, rq[3]):
            raise ValueError(f"request {j}: bad path {rq[3]!r}")
    answers = []
    for user, groups, action, path in requests:
        hits = []
        for i, eff, pr, ac, rs in table:
            if pr == "*":
                pw = 0
            elif pr == "user:" + user:
                pw = 2
            elif pr.startswith("group:") and pr[6:] in groups:
                pw = 1
            else:
                continue
            if ac != "*" and action not in ac.split(","):
                continue
            pat = _segs(rs)
            if not _m(pat, _segs(path)):
                continue
            lit = len([x for x in pat if x != "*" and x != "**"])
            hits.append(((lit, pw, 0 if ac == "*" else 1), eff, i))
        if not hits:
            answers.append("DENY by default")
            continue
        top = max(h[0] for h in hits)
        tied = [h for h in hits if h[0] == top]
        denies = [h for h in tied if h[1] == "DENY"]
        pick = min(denies or tied, key=lambda h: h[2])
        answers.append(f"{pick[1]} by rule {pick[2]}")
    return answers
