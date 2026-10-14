N = 800

DATES = ["2024-02-28", "2024-02-29", "2024-03-01", "2024-03-01", "2024-03-02", "2025-01-01"]
BAD_DATES = ["2023-02-29", "1900-02-29", "2000-02-29", "2024-13-01", "2024-1-01", "24-01-01", "2024/01/01",
             "1899-12-31", "3000-01-01", "2024-04-31", "２０２４-01-01", None, 20240101, "2024-01-01 "]
AMOUNTS = ["1", "0.5", "0.05", "25", "25.00", "999999999.99", "1000", "12.3", "7.25", "100000"]
BAD_AMOUNTS = ["0", "0.0", "0.00", "01", "1.", ".5", "1.234", "-5", "+5", "1e3", "1,000", 5, 5.0, None,
               "1000000000", " 5", "5 ", "00.50"]
MEMOS = ["x", "rent", "  pay   check ", "a" * 20, "b" * 21, "word " * 6, "café   bar", "OVERDRAFT FEE"]
BAD_MEMOS = ["", "   ", "tab\there", "nl\n", "del\x7f", 5, None, " "]
OPENINGS = ["0.00", "-0.00", "10.00", "-5.25", "1000000.00", "999999999.99", "30.00", "0.01"]
BAD_OPENINGS = ["5", "5.0", "05.00", "-", "+1.00", "1.000", 5, None, " 1.00", "1,000.00", "--1.00"]


def gen(rng):
    opening = rng.choice(OPENINGS)
    n = rng.randint(0, 9)
    dates = sorted(rng.choice(DATES) for _ in range(n))
    entries = []
    for d in dates:
        kind = rng.choice(["credit", "debit", "debit", "debit", "fee"])
        entries.append((d, kind, rng.choice(AMOUNTS), rng.choice(MEMOS)))
    r = rng.random()
    if r < 0.45 or not entries:
        if rng.random() < 0.15:
            opening = rng.choice(BAD_OPENINGS)
        elif rng.random() < 0.05:
            entries = tuple(entries)
        return (opening, entries)
    i = rng.randrange(len(entries))
    d, k, a, m = entries[i]
    what = rng.randrange(7)
    if what == 0:
        entries[i] = rng.choice([[d, k, a, m], (d, k, a), (d, k, a, m, m), "x"])
    elif what == 1:
        entries[i] = (rng.choice(BAD_DATES), k, a, m)
    elif what == 2:
        entries[i] = ("1999-12-31", k, a, m)
    elif what == 3:
        entries[i] = (d, rng.choice(["Credit", "refund", "", None, "fee "]), a, m)
    elif what == 4:
        entries[i] = (d, k, rng.choice(BAD_AMOUNTS), m)
    elif what == 5:
        entries[i] = (d, k, a, rng.choice(BAD_MEMOS))
    else:
        j = rng.randrange(len(entries))
        entries[j] = (rng.choice(BAD_DATES), rng.choice(["x", "debit"]), rng.choice(BAD_AMOUNTS), rng.choice(BAD_MEMOS))
    return (opening, entries)
