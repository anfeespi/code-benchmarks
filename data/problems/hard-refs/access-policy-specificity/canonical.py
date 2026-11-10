NAME_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_")
SEG_CHARS = NAME_CHARS | set(".-")
ACTION_CHARS = set("abcdefghijklmnopqrstuvwxyz")


def _name_ok(s):
    return isinstance(s, str) and s != "" and all(c in NAME_CHARS for c in s)


def _segments(path, allow_wild):
    if not isinstance(path, str) or not path.startswith("/"):
        return None
    if path == "/":
        return []
    segs = path[1:].split("/")
    for s in segs:
        if allow_wild and s in ("*", "**"):
            continue
        if not s or any(c not in SEG_CHARS for c in s):
            return None
    return segs


def _parse_rule(i, rule):
    if not isinstance(rule, str):
        raise TypeError("rule %d: not a str" % i)
    f = rule.split()
    if len(f) != 4:
        raise ValueError("rule %d: expected 4 fields, got %d" % (i, len(f)))
    effect, principal, action, resource = f
    if effect not in ("ALLOW", "DENY"):
        raise ValueError("rule %d: bad effect %r" % (i, effect))
    if principal == "*":
        pk = ("any", None)
    elif principal.startswith("user:") and _name_ok(principal[5:]):
        pk = ("user", principal[5:])
    elif principal.startswith("group:") and _name_ok(principal[6:]):
        pk = ("group", principal[6:])
    else:
        raise ValueError("rule %d: bad principal %r" % (i, principal))
    if action == "*":
        acts = None
    else:
        acts = action.split(",")
        if any(not a or any(c not in ACTION_CHARS for c in a) for a in acts):
            raise ValueError("rule %d: bad action %r" % (i, action))
        acts = set(acts)
    segs = _segments(resource, True)
    if segs is None:
        raise ValueError("rule %d: bad resource %r" % (i, resource))
    literal = sum(1 for s in segs if s not in ("*", "**"))
    spec = (literal, {"user": 2, "group": 1, "any": 0}[pk[0]], 0 if acts is None else 1)
    return {"deny": effect == "DENY", "pk": pk, "acts": acts, "segs": segs, "spec": spec, "idx": i}


def _match(pat, path):
    # DP over (pattern position, path position); "**" consumes zero or more segments
    n, m = len(pat), len(path)
    reach = [False] * (m + 1)
    reach[0] = True
    for p in pat:
        nxt = [False] * (m + 1)
        if p == "**":
            run = False
            for j in range(m + 1):
                run = run or reach[j]
                nxt[j] = run
        else:
            for j in range(m):
                if reach[j] and (p == "*" or p == path[j]):
                    nxt[j + 1] = True
        reach = nxt
        if not any(reach):
            return False
    return reach[m]


def evaluate_access(rules, requests):
    if not isinstance(rules, list):
        raise TypeError("rules must be a list")
    if not isinstance(requests, list):
        raise TypeError("requests must be a list")
    parsed = [_parse_rule(i, r) for i, r in enumerate(rules)]
    reqs = []
    for j, rq in enumerate(requests):
        if not isinstance(rq, tuple) or len(rq) != 4:
            raise TypeError("request %d: expected 4-tuple" % j)
        user, groups, action, path = rq
        if not _name_ok(user):
            raise ValueError("request %d: bad user %r" % (j, user))
        if not isinstance(groups, list) or not all(_name_ok(g) for g in groups):
            raise ValueError("request %d: bad groups" % j)
        if not isinstance(action, str) or not action or any(c not in ACTION_CHARS for c in action):
            raise ValueError("request %d: bad action %r" % (j, action))
        segs = _segments(path, False)
        if segs is None:
            raise ValueError("request %d: bad path %r" % (j, path))
        reqs.append((user, set(groups), action, segs))
    # most specific first; within equal specificity DENY first, then lowest index
    ordered = sorted(parsed, key=lambda r: (-r["spec"][0], -r["spec"][1], -r["spec"][2], not r["deny"], r["idx"]))
    out = []
    for user, groups, action, segs in reqs:
        verdict = "DENY by default"
        for r in ordered:
            kind, name = r["pk"]
            if kind == "user" and name != user:
                continue
            if kind == "group" and name not in groups:
                continue
            if r["acts"] is not None and action not in r["acts"]:
                continue
            if not _match(r["segs"], segs):
                continue
            verdict = "%s by rule %d" % ("DENY" if r["deny"] else "ALLOW", r["idx"])
            break
        out.append(verdict)
    return out
