Write a Python function:

    def decimal_to_half_bits(s: str) -> int

It converts a decimal literal to the IEEE 754 binary16 ("half precision") value that is
nearest to the EXACT value of the literal, and returns the 16-bit pattern as an int in
`0 .. 65535`.

Literal grammar (the whole string must match; no surrounding whitespace, no underscores,
only the ASCII digits 0-9):

    literal  := [sign] mantissa [exponent]
    sign     := "+" | "-"
    mantissa := digits | digits "." | digits "." digits | "." digits
    exponent := ("e" | "E") [sign] digits
    digits   := one or more of 0-9

Anything else (including a non-str argument, "inf", "nan", "", ".", "1e", " 1", "1_0")
raises ValueError.

binary16 format: bit 15 is the sign, bits 14-10 are the biased exponent E (bias 15),
bits 9-0 are the fraction F.
- E = 0: subnormal (or zero), value = F * 2**-24.
- 1 <= E <= 30: normal, value = (1 + F/1024) * 2**(E-15).
- E = 31 with F = 0 is infinity (0x7C00 / 0xFC00). Never return a NaN pattern.
The largest finite value is 65504 (0x7BFF); the smallest positive value is 2**-24 (0x0001).

Rounding (round-to-nearest, ties-to-even, as IEEE 754 specifies):
- Let v = |exact value of the literal|. Choose the finite non-negative binary16 value
  nearest to v, where the ordered list of candidates is extended past 65504 by 65536
  (which stands for infinity). If v is exactly halfway between two adjacent candidates,
  choose the one whose 16-bit pattern is even (the pattern of 65536 is taken to be 0x7C00,
  which is even). Any v >= 65536 gives infinity. Consequently every v >= 65520 is
  infinity, and every v <= 2**-25 rounds to zero.
- The result's sign bit is 1 exactly when the literal starts with "-", even if the
  value rounds to zero or is zero ("-0" -> 0x8000, "-1e-30" -> 0x8000, "+0" -> 0).

The rounding must be applied ONCE to the exact decimal value. Converting to a Python
float first and then to binary16 rounds twice and is wrong for some inputs.

Input domain: the literal may be up to 200,000 characters long, and the exponent may
have many digits (e.g. "1e999999999999" or "7e-0000000000000000000000000003"); the
function must still return quickly (well under a second).

Examples:
- decimal_to_half_bits("1") == 0x3C00
- decimal_to_half_bits("-2.5") == 0xC100
- decimal_to_half_bits("65519.99") == 0x7BFF
- decimal_to_half_bits("65520") == 0x7C00
- decimal_to_half_bits("1.00048828125") == 0x3C00      # exact tie between 1 and 1+2**-10 -> even pattern
- decimal_to_half_bits("1.000488281250000000001") == 0x3C01
- decimal_to_half_bits("2.98023223876953125e-8") == 0x0000   # exactly 2**-25: tie -> 0
- decimal_to_half_bits("-1e999999999") == 0xFC00
- decimal_to_half_bits("0.1") == 0x2E66
