DIG = "0123456789"


def _num(s):
    if not s or any(c not in DIG for c in s) or (len(s) > 1 and s[0] == "0"):
        return None
    return int(s)


def _version(s):
    """'X.Y.Z' or 'X.Y.Z~rcN' -> sortable key (X, Y, Z, released, N) or None."""
    if not isinstance(s, str):
        return None
    rc = None
    if "~" in s:
        s, tail = s.split("~", 1)
        if not tail.startswith("rc"):
            return None
        rc = _num(tail[2:])
        if rc is None or rc < 1:
            return None
    parts = s.split(".")
    if len(parts) != 3:
        return None
    nums = [_num(p) for p in parts]
    if None in nums:
        return None
    return (nums[0], nums[1], nums[2], 0 if rc is not None else 1, rc or 0)


def _clause(text):
    """Return a predicate over version keys, or None if the clause is invalid."""
    if text == "*":
        return lambda k: True
    if text.startswith("@"):
        parts = text[1:].split(".")
        if len(parts) != 2:
            return None
        x, y = _num(parts[0]), _num(parts[1])
        if x is None or y is None:
            return None
        return lambda k: k[0] == x and k[1] >= y
    if text.endswith(".*"):
        parts = text[:-2].split(".")
        if not 1 <= len(parts) <= 2:
            return None
        nums = [_num(p) for p in parts]
        if None in nums:
            return None
        return lambda k: list(k[:len(nums)]) == nums
    for op in (">=", "<=", "!=", ">", "<", "="):
        if text.startswith(op):
            v = _version(text[len(op):])
            if v is None:
                return None
            return {">=": lambda k: k >= v, "<=": lambda k: k <= v, "!=": lambda k: k != v,
                    ">": lambda k: k > v, "<": lambda k: k < v, "=": lambda k: k == v}[op]
    v = _version(text)
    if v is None:
        return None
    return lambda k: k == v


def pick_version(available, constraint):
    if not isinstance(available, list):
        raise TypeError("available must be a list")
    keys = []
    for i, s in enumerate(available):
        k = _version(s)
        if k is None:
            raise ValueError("invalid version at index %d: %r" % (i, s))
        keys.append(k)
    if not isinstance(constraint, str):
        raise TypeError("constraint must be a str")
    if constraint.strip(" ") == "":
        raise ValueError("empty constraint")
    alternatives = []
    for a, alt in enumerate(constraint.split("|"), 1):
        alt = alt.strip(" ")
        rc_ok = alt.startswith("?")
        if rc_ok:
            alt = alt[1:].strip(" ")
        if not alt:
            raise ValueError("alternative %d is empty" % a)
        preds = []
        for c, clause in enumerate(alt.split(","), 1):
            clause = clause.strip(" ")
            p = _clause(clause)
            if p is None:
                raise ValueError("alternative %d, clause %d: invalid clause %r" % (a, c, clause))
            preds.append(p)
        alternatives.append((rc_ok, preds))
    best = None
    for s, k in zip(available, keys):
        if best is not None and k <= best[0]:
            continue
        for rc_ok, preds in alternatives:
            if (k[3] == 1 or rc_ok) and all(p(k) for p in preds):
                best = (k, s)
                break
    return best[1] if best else None
