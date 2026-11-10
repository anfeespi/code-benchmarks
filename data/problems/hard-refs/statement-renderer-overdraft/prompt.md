Write a Python function:

    def render_statement(opening, entries) -> list[str]

It validates a list of account entries and renders a plain-text account statement.

INPUTS
- `opening`: the opening balance as a str matching `-?(0|[1-9][0-9]{0,8})\.[0-9]{2}`
  (optional minus sign, integer part without leading zeros and at most 9 digits, EXACTLY
  two decimals). "-0.00" is accepted and means zero.
- `entries`: a list of 4-tuples `(date, kind, amount, memo)`.

VALIDATION (performed completely before any output is produced; the FIRST failure raises)
1. If `opening` is not a str: raise TypeError("opening must be a str").
2. If `opening` does not match the pattern above: raise ValueError("opening: bad amount " + repr(opening)).
3. If `entries` is not a list: raise TypeError("entries must be a list").
4. Then entries are checked one at a time in list order (index `i` is 0-based). For each
   entry the checks run in this order and the first failing one raises:
   a. not a tuple, or a tuple whose length is not 4 -> TypeError(f"entry {i}: expected 4-tuple")
   b. `date` is not a str of the form YYYY-MM-DD (exactly 4, 2 and 2 ASCII digits separated
      by "-") naming a real Gregorian calendar date with year in 1900..2999
      -> ValueError(f"entry {i}: bad date {date!r}")
   c. `date` is earlier than the date of entry i-1 (equal dates are fine)
      -> ValueError(f"entry {i}: date out of order")
   d. `kind` is not one of the strs "credit", "debit", "fee"
      -> ValueError(f"entry {i}: bad kind {kind!r}")
   e. `amount` is not a str matching `(0|[1-9][0-9]{0,8})(\.[0-9]{1,2})?` (no sign, integer
      part without leading zeros and at most 9 digits, optionally a dot followed by one or two
      digits), or its value is zero -> ValueError(f"entry {i}: bad amount {amount!r}")
   f. `memo` is not a str, or contains no non-whitespace characters (i.e. `memo.split()` is
      empty), or contains any character whose code point is below 32 or equal to 127
      -> ValueError(f"entry {i}: bad memo")
All regular-expression patterns above must match the WHOLE string.

PROCESSING
The running balance starts at `opening`. Entries are applied in order: a "credit" adds its
amount, a "debit" or a "fee" subtracts its amount. All arithmetic must be exact (cents).

Automatic overdraft fee: immediately after applying a "debit" entry, if the balance is now
strictly negative AND no automatic overdraft fee has been inserted yet for that entry's date,
insert an automatic fee entry right after it: same date, kind "fee", amount 25.00, memo
"OVERDRAFT FEE". It is applied (subtracted) and rendered like any other fee. At most one
automatic fee per distinct date; manual "fee" entries never trigger one and do not count as
one; credits and fees never trigger one.

OUTPUT: a list of lines (strs, no newline characters):
- First line: "Opening balance: " + MONEY(opening balance)
- One line per applied entry (including automatic fees), in order:
      f"{date}  {MEMO}  {AMT}  {BAL}{FLAG}"
  (exactly two spaces between columns), where
  - MEMO: the memo with its whitespace normalized as `" ".join(memo.split())`; if the result
    is longer than 20 characters it becomes its first 19 characters followed by "~"; then it
    is left-justified (padded with spaces on the right) to width 20.
  - AMT: "+" for credits, "-" for debits and fees, followed by MONEY(amount), right-justified
    to width 14 (padded with spaces on the left; longer values are not truncated).
  - BAL: MONEY(balance after this entry), right-justified to width 15 (not truncated).
  - FLAG: " OD" if the balance after this entry is strictly negative, else "".
- Then "Closing balance: " + MONEY(final balance)
- Last line: f"Credits: {c}  Debits: {d}  Fees: {f}" with the number of credit, debit and fee
  lines rendered (automatic fees count as fees).
MONEY(x): "-" if x < 0 (never "+", and zero is never negative), then the integer part of |x|
with "," as the thousands separator, then "." and exactly two decimal digits.
e.g. 1234567.5 -> "1,234,567.50", -0.05 -> "-0.05", 0 -> "0.00".

Examples:
    render_statement("10.00", [("2024-03-01", "debit", "15", "rent part"),
                               ("2024-03-01", "debit", "1.5", "snack"),
                               ("2024-03-02", "credit", "1000", "  pay   check  ")])
    == ["Opening balance: 10.00",
        "2024-03-01  rent part                     -15.00            -5.00 OD",
        "2024-03-01  OVERDRAFT FEE                 -25.00           -30.00 OD",
        "2024-03-01  snack                          -1.50           -31.50 OD",
        "2024-03-02  pay check                  +1,000.00           968.50",
        "Closing balance: 968.50",
        "Credits: 1  Debits: 2  Fees: 1"]
    (the second debit on 2024-03-01 gets no fee: that date already had its automatic fee)

    render_statement("0.00", [("2024-01-02", "fee", "3", "x"), ("2024-01-01", "credit", "5", "y")])
        raises ValueError("entry 1: date out of order")
    render_statement("5", [])
        raises ValueError("opening: bad amount '5'")
