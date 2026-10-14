DIGITS = "0123456789"


def _days_in_month(y, m):
    if m == 2:
        return 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28
    return 30 if m in (4, 6, 9, 11) else 31


def _valid_date(s):
    if not isinstance(s, str) or len(s) != 10 or s[4] != "-" or s[7] != "-":
        return False
    parts = (s[0:4], s[5:7], s[8:10])
    if not all(ch in DIGITS for p in parts for ch in p):
        return False
    y, m, d = (int(p) for p in parts)
    return 1900 <= y <= 2999 and 1 <= m <= 12 and 1 <= d <= _days_in_month(y, m)


def _int_part_ok(s, max_len):
    if not s or len(s) > max_len or any(ch not in DIGITS for ch in s):
        return False
    return not (len(s) > 1 and s[0] == "0")


def _parse_amount(s):
    """Entry amount -> positive cents, or None."""
    if not isinstance(s, str):
        return None
    if "." in s:
        ip, fp = s.split(".", 1)
        if not (1 <= len(fp) <= 2) or any(ch not in DIGITS for ch in fp):
            return None
    else:
        ip, fp = s, ""
    if not _int_part_ok(ip, 9):
        return None
    cents = int(ip) * 100 + int((fp + "00")[:2])
    return cents if cents > 0 else None


def _parse_opening(s):
    if not isinstance(s, str):
        return None
    neg = s.startswith("-")
    body = s[1:] if neg else s
    if body.count(".") != 1:
        return None
    ip, fp = body.split(".")
    if len(fp) != 2 or any(ch not in DIGITS for ch in fp) or not _int_part_ok(ip, 9):
        return None
    v = int(ip) * 100 + int(fp)
    return -v if neg else v


def _money(c):
    sign = "-" if c < 0 else ""
    c = abs(c)
    whole = str(c // 100)
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    return sign + ",".join(groups) + "." + str(c % 100).rjust(2, "0")


def _memo_ok(m):
    if not isinstance(m, str) or not m.split():
        return False
    return not any(ord(ch) < 32 or ord(ch) == 127 for ch in m)


def _memo_col(m):
    m = " ".join(m.split())
    if len(m) > 20:
        m = m[:19] + "~"
    return m.ljust(20)


def render_statement(opening, entries):
    if not isinstance(opening, str):
        raise TypeError("opening must be a str")
    bal = _parse_opening(opening)
    if bal is None:
        raise ValueError("opening: bad amount %r" % (opening,))
    if not isinstance(entries, list):
        raise TypeError("entries must be a list")
    parsed = []
    prev = None
    for i, e in enumerate(entries):
        if not isinstance(e, tuple) or len(e) != 4:
            raise TypeError("entry %d: expected 4-tuple" % i)
        date, kind, amount, memo = e
        if not _valid_date(date):
            raise ValueError("entry %d: bad date %r" % (i, date))
        if prev is not None and date < prev:
            raise ValueError("entry %d: date out of order" % i)
        prev = date
        if kind not in ("credit", "debit", "fee") or not isinstance(kind, str):
            raise ValueError("entry %d: bad kind %r" % (i, kind))
        cents = _parse_amount(amount)
        if cents is None:
            raise ValueError("entry %d: bad amount %r" % (i, amount))
        if not _memo_ok(memo):
            raise ValueError("entry %d: bad memo" % i)
        parsed.append((date, kind, cents, memo))

    lines = ["Opening balance: " + _money(bal)]
    counts = {"credit": 0, "debit": 0, "fee": 0}
    od_dates = set()

    def emit(date, kind, cents, memo):
        nonlocal bal
        bal += cents if kind == "credit" else -cents
        counts[kind] += 1
        amt = ("+" if kind == "credit" else "-") + _money(cents)
        lines.append("%s  %s  %s  %s%s" % (date, _memo_col(memo), amt.rjust(14), _money(bal).rjust(15),
                                           " OD" if bal < 0 else ""))

    for date, kind, cents, memo in parsed:
        emit(date, kind, cents, memo)
        if kind == "debit" and bal < 0 and date not in od_dates:
            od_dates.add(date)
            emit(date, "fee", 2500, "OVERDRAFT FEE")
    lines.append("Closing balance: " + _money(bal))
    lines.append("Credits: %d  Debits: %d  Fees: %d" % (counts["credit"], counts["debit"], counts["fee"]))
    return lines
