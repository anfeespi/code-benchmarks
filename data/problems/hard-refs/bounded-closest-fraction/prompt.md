Write a Python function:

    def closest_fraction(x: str, max_num: int, max_den: int) -> str

`x` is a decimal literal. Among all fractions a/b with integers a, b such that
`|a| <= max_num` and `1 <= b <= max_den`, return the one whose value is closest to the
EXACT value of `x`.

Literal grammar (the whole string must match; ASCII digits only, no whitespace, no
underscores):

    literal  := [sign] mantissa [exponent]
    sign     := "+" | "-"
    mantissa := digits | digits "." | digits "." digits | "." digits
    exponent := ("e" | "E") [sign] digits
    digits   := one or more of 0-9

Validation: raise ValueError if `x` does not match the grammar (including "inf", "nan",
"", " 1", "1_0"), if `max_num < 0`, or if `max_den < 1`.

Selection rule:
- Compare candidates by their VALUE; fractions with equal value are the same candidate
  (2/4 and 1/2 are one candidate, written in lowest terms as 1/2).
- The answer is the candidate with the smallest |value - x|.
- If two different candidates are equally close (one below x, one above), choose the one
  whose lowest-terms denominator is smaller; if those denominators are equal too, choose
  the one with the smaller absolute value (the one closer to zero).

Output: the chosen fraction in lowest terms as "a/b" with b >= 1 and the sign (if any) on
the numerator, e.g. "-3/7", "5/1", "0/1" (zero is always "0/1", never "-0/1").

Input domain: the mantissa has at most 1000 digits, the exponent's absolute value is at
most 1000, and 0 <= max_num <= 10**18, 1 <= max_den <= 10**18. Each call must take well
under a second even with both bounds near 10**18 (iterating over denominators is far too
slow).

Examples:
- closest_fraction("3.14159", 1000, 100) == "311/99"
- closest_fraction("3.14159", 10, 100) == "3/1"      # the numerator bound binds
- closest_fraction("0.3", 1, 10) == "1/3"
- closest_fraction("0.25", 5, 2) == "0/1"           # 0/1 and 1/2 are equally close; denominator 1 < 2
- closest_fraction("-0.5", 1, 1) == "0/1"           # -1/1 and 0/1 tie with equal denominators; 0 is closer to zero
- closest_fraction("-2.75", 2, 4) == "-2/1"         # |a| <= 2 caps the value at -2
- closest_fraction("1e-3", 3, 10) == "0/1"
