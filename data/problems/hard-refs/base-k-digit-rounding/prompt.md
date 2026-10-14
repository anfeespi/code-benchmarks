Write a Python function:

    def format_base(p: int, q: int, base: int, k: int) -> str

It renders the rational number x = p / q in positional notation in base `base`, rounded
to `k` digits after the radix point.

Validation: raise ValueError if `q == 0`, if `base` is not in `2 .. 36`, or if `k < 0`.
(All four arguments are ints; `p` and `q` may be negative.)

Rounding rule (exact, no floating point):
- Let N be the integer nearest to |x| * base**k. If |x| * base**k is exactly halfway
  between two integers, N is the EVEN one of the two. Note that this is the parity of the
  integer N itself, not of its last digit: in an odd base those can differ
  (e.g. in base 3, N = 4 is written "11").
- The rounded magnitude is N / base**k.

Output format:
- If N == 0 the result is "0" (never "-0", never a radix point).
- Otherwise write N / base**k as: the integer part N // base**k in base `base` (no leading
  zeros; "0" if it is zero), then, if N mod base**k != 0, a "." followed by the k
  fractional digits of N mod base**k (left-padded with zeros to exactly k digits) with
  trailing zeros removed. If N mod base**k == 0 there is no "." at all.
- Digits are 0-9 then lowercase a-z for values 10-35.
- Prefix "-" when x < 0 (and N != 0).

Input domain: |p| and |q| up to 10**600, k up to 300,000.

Performance requirement: calls with k around 300,000 (base 7, base 10 and base 36,
moderate p and q) must each finish in well under a second. Building the big integer N and
converting it to base `base` by repeatedly dividing the whole number by `base` is
quadratic in k and too slow. Python's built-in int-to-str conversion is also limited to
4300 decimal digits by default.

Examples:
- format_base(1, 3, 10, 2) == "0.33"
- format_base(-5, 2, 10, 0) == "-2"        # 2.5 is a tie -> even N = 2
- format_base(7, 2, 3, 0) == "11"          # 3.5 is a tie between 3 and 4 -> N = 4 = "11" in base 3
- format_base(5, 6, 3, 1) == "0.2"         # 5/6 * 3 = 2.5 -> N = 2
- format_base(-1, 4, 10, 0) == "0"         # rounds to zero: no minus sign
- format_base(255, 16, 16, 1) == "f.f"
- format_base(-1, -3, 2, 5) == "0.01011"   # 1/3 * 32 = 10.67 -> N = 11 = 01011 in 5 binary digits
