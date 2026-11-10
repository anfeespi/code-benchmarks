import datetime
import re
from decimal import Decimal

AMOUNT_RE = re.compile(r"(0|[1-9][0-9]{0,8})(\.[0-9]{1,2})?")
OPEN_RE = re.compile(r"-?(0|[1-9][0-9]{0,8})\.[0-9]{2}")
DATE_RE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")


def _date(s):
    if type(s) is not str:
        return None
    m = DATE_RE.fullmatch(s)
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    if not 1900 <= y <= 2999:
        return None
    try:
        return datetime.date(y, mo, d)
    except ValueError:
        return None


def _fmt(d):
    return format(d, ",.2f").replace("-0.00", "0.00")


def render_statement(opening, entries):
    if type(opening) is not str:
        raise TypeError("opening must be a str")
    if not OPEN_RE.fullmatch(opening):
        raise ValueError("opening: bad amount " + repr(opening))
    balance = Decimal(opening)
    if type(entries) is not list:
        raise TypeError("entries must be a list")
    last = None
    for idx in range(len(entries)):
        row = entries[idx]
        if type(row) is not tuple or len(row) != 4:
            raise TypeError(f"entry {idx}: expected 4-tuple")
        d = _date(row[0])
        if d is None:
            raise ValueError(f"entry {idx}: bad date {row[0]!r}")
        if last is not None and d < last:
            raise ValueError(f"entry {idx}: date out of order")
        last = d
        if type(row[1]) is not str or row[1] not in {"credit", "debit", "fee"}:
            raise ValueError(f"entry {idx}: bad kind {row[1]!r}")
        a = row[2]
        if type(a) is not str or not AMOUNT_RE.fullmatch(a) or Decimal(a) == 0:
            raise ValueError(f"entry {idx}: bad amount {a!r}")
        memo = row[3]
        if type(memo) is not str or memo.split() == [] or re.search(r"[\x00-\x1f\x7f]", memo):
            raise ValueError(f"entry {idx}: bad memo")

    out = [f"Opening balance: {_fmt(balance)}"]
    n_credit = n_debit = n_fee = 0
    charged = []
    todo = []
    for row in entries:
        todo.append(row)
    k = 0
    while k < len(todo):
        date, kind, amt, memo = todo[k]
        value = Decimal(amt)
        if kind == "credit":
            balance = balance + value
            n_credit += 1
            sign = "+"
        else:
            balance = balance - value
            sign = "-"
            if kind == "debit":
                n_debit += 1
            else:
                n_fee += 1
        words = memo.split()
        shown = " ".join(words)
        if len(shown) > 20:
            shown = shown[:19] + "~"
        line = date + "  " + f"{shown:<20}" + "  " + f"{sign + _fmt(value):>14}" + "  " + f"{_fmt(balance):>15}"
        if balance < 0:
            line += " OD"
        out.append(line)
        if kind == "debit" and balance < 0 and date not in charged:
            charged.append(date)
            todo.insert(k + 1, (date, "fee", "25.00", "OVERDRAFT FEE"))
        k += 1
    out.append(f"Closing balance: {_fmt(balance)}")
    out.append(f"Credits: {n_credit}  Debits: {n_debit}  Fees: {n_fee}")
    return out
