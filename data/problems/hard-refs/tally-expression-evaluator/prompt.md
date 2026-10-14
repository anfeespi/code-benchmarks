Write a Python function:

    def evaluate(src: str, env: dict) -> tuple

that parses and evaluates one expression of the small integer language "Tally".
`env` maps variable names (str) to ints. The function never raises: it returns
`("ok", value)` on success, or `("error", pos, message)` where `pos` is a 0-based
character index into `src` and `message` is one of the exact strings listed below.

TOKENS (scan left to right, longest match first):
- Spaces (' ') separate tokens and are otherwise ignored. No other whitespace exists in
  the language (a tab or newline is an invalid character).
- INT: a maximal run of ASCII digits '0'-'9' (leading zeros allowed: "007" is 7).
- NAME: an ASCII lowercase letter or '_' followed by a maximal run of ASCII lowercase
  letters, digits and '_'. ("12ab" is the INT 12 followed by the NAME ab.)
- Two-character operators: '<=' '>=' '==' '!='  (tried before one-character operators)
- One-character operators: '+' '-' '*' '/' '%' '^' '(' ')' '?' ':' '<' '>'
- Any other character (including uppercase letters, '=' or '!' not part of a
  two-character operator, '.', tabs, non-ASCII) is an INVALID CHARACTER token of length 1.
- The end of the input is a special END token at position len(src).

GRAMMAR (lowest to highest precedence):

    expr  := cond END
    cond  := cmp [ '?' cond ':' cond ]           ternary, right-associative
    cmp   := sum [ cmpop sum ]                    cmpop: < <= > >= == !=  (NON-associative)
    sum   := term { ('+' | '-') term }            left-associative
    term  := unary { ('*' | '/' | '%') unary }    left-associative
    unary := '-' unary | power                    prefix minus, binds LOOSER than '^'
    power := atom [ '^' unary ]                   right-associative; exponent may be negated
    atom  := INT | NAME | '(' cond ')'

So -2^2 is -(2^2) = -4, 2^3^2 is 2^(3^2) = 512, 2^-1 is 2^(-(1)), and `a < b < c` is a
syntax error, while `(a < b) < c` is fine.

SYNTAX ERRORS. The entire input is tokenized and parsed before anything is evaluated.
If the token sequence is not a valid `expr`, report the FIRST token (leftmost) at which
the tokens read so far, including that token, are no longer the beginning of any valid
`expr` (this is exactly where a standard recursive-descent parser for the grammar above
first fails). Report its start position and the message:
- "unexpected end of input"        if that token is END
- "unexpected character 'C'"       if it is an INVALID CHARACTER C (C is the character itself)
- "unexpected token 'T'"           otherwise, T being the token's exact text

EVALUATION (only for syntactically valid input). Values are Python ints (unbounded).
- INT -> its value. NAME -> env[name]; if absent: error "unknown name 'NAME'" at the
  NAME's position.
- Binary operators evaluate the left operand completely, then the right operand, then
  apply the operator. '+', '-', '*' as usual. '/' is floor division and '%' the matching
  modulo (Python's // and %: -7/2 = -4, -7%2 = 1, 7%-2 = -1); a zero right operand is the
  error "division by zero" at the position of the '/' or '%' character.
- '^' is exponentiation. After evaluating both sides: if the exponent is negative, error
  "negative exponent"; else if it is greater than 256, error "exponent too large"; both at
  the position of the '^'. 0^0 = 1.
- Comparisons produce 1 if true and 0 if false.
- Prefix '-' negates.
- `c ? a : b` evaluates c first; if c != 0 it evaluates and returns a, otherwise it
  evaluates and returns b. The branch not taken is NEVER evaluated (errors inside it,
  such as division by zero or unknown names, do not happen).
- The first error in this evaluation order is reported.

Inputs can be large: up to 400,000 characters, parentheses nested up to 30,000 deep,
prefix-minus chains and '^' chains up to 30,000 long, and operator chains of 100,000
operands. Your function must handle these without crashing (mind Python's default
recursion limit of 1000) and run in a few seconds.

Examples:
- evaluate("-2^2 + 2^3^2", {}) == ("ok", 508)
- evaluate("-7/2 + -7%2*10", {}) == ("ok", 6)
- evaluate("x > 1 ? 10 / (x - 3) : 0", {"x": 0}) == ("ok", 0)
- evaluate("a < b < c", {"a": 1, "b": 2, "c": 3}) == ("error", 6, "unexpected token '<'")
- evaluate("3 * (4 + y", {}) == ("error", 10, "unexpected end of input")
  # the syntax error wins even though y is unknown: nothing is evaluated
- evaluate("n = 3", {"n": 1}) == ("error", 2, "unexpected character '='")
- evaluate("8 % (k - k)", {"k": 5}) == ("error", 2, "division by zero")
- evaluate("2^-1", {}) == ("error", 1, "negative exponent")
