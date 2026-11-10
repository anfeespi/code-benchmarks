Write a Python function:

    def amortize(principal: str, annual_rate_pct: str, months: int) -> list[tuple[str, str, str]]

It produces the payment schedule of a fixed-payment loan, computed with EXACT rational
arithmetic and the rounding rules below (no binary floating point anywhere: results must
be exact to the cent for any valid input).

Inputs and validation (raise ValueError on any violation):
- `principal`: a str matching `digits` or `digits "." d` or `digits "." d d` (ASCII
  digits only; at least one digit before the point; one or two digits after it if a point
  is present). Its value must be > 0. Leading zeros are allowed.
- `annual_rate_pct`: an annual interest rate in PERCENT, a str matching `digits` or
  `digits "." 1-to-6 digits` (e.g. "6", "6.5", "0.000001"). Its value must be <= 100.
  Zero is allowed.
- `months`: an int with 1 <= months <= 1200.

Definitions (all exact): P = principal, n = months, m = annual_rate_pct / 100 / 12 (the
monthly rate, an exact rational).

1. Level payment: A = P / n if m == 0, otherwise A = P * m / (1 - (1 + m) ** (-n)).
   PAY = A rounded UP to a whole cent (the smallest multiple of 0.01 that is >= A; if A
   is already a whole number of cents, PAY == A).
2. Start with BAL = P. For t = 1, 2, ..., n:
   - INTEREST = BAL * m rounded to a whole cent, ties (exactly half a cent) going to the
     EVEN number of cents.
   - If t == n, or BAL + INTEREST <= PAY: this is the final row. The payment is
     BAL + INTEREST, the new balance is 0, and the schedule ends here (possibly before
     month n).
   - Otherwise the payment is PAY and the new balance is BAL - (PAY - INTEREST).
3. Each row is the tuple (payment, interest, balance_after), each formatted as a str with
   an integer part (no leading zeros except a single "0", no sign, no thousands
   separators), a ".", and exactly two decimals, e.g. "0.05", "1074.65", "0.00".

Return the list of rows in order.

Input domain: principal up to 30 integer digits. A call with months = 1200 must finish
well under a second.

Examples:
- amortize("1000", "12", 1) == [("1010.00", "10.00", "0.00")]
- amortize("100", "0", 3) == [("33.34", "0.00", "66.66"), ("33.34", "0.00", "33.32"), ("33.32", "0.00", "0.00")]
- amortize("201", "12", 2) == [("102.01", "2.01", "101.00"), ("102.01", "1.01", "0.00")]
- amortize("250", "3", 2) == [("125.47", "0.62", "125.15"), ("125.46", "0.31", "0.00")]
  # month 1 interest is exactly 62.5 cents -> ties to even -> 0.62
- amortize("1000", "6", 3) == [("336.68", "5.00", "668.32"), ("336.68", "3.34", "334.98"), ("336.65", "1.67", "0.00")]
