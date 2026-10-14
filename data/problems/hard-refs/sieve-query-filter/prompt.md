Write a Python function:

    def filter_records(query: str, records: list[dict]) -> tuple

that evaluates a query in the filter language "Sieve" against every record and returns
`("ok", indices)` — the ascending list of indices `i` such that the query is TRUE for
`records[i]` — or `("error", pos, message)` if the query is invalid, where `pos` is a
0-based character index into `query` and `message` is one of the exact strings below.
The function never raises. Each record is a dict mapping str field names to values that
are either int (never bool) or str.

STEP 1 — LEXING. The whole query is tokenized left to right before parsing; the first
lexical error stops everything (even if a syntax error would occur earlier). Tokens:
- Whitespace ' ', '\t', '\n' separates tokens and is skipped.
- Punctuation: '(' ')' '[' ']' ','.
- Comparison operators: '!=' '<=' '>=' (two characters, tried first), then '=' '<' '>'.
- INT: optional '-' immediately followed by one or more ASCII digits, then all following
  ASCII digits (maximal). A '-' not immediately followed by a digit is an unexpected
  character.
- STRING: starts with '"'. Characters up to the first unescaped '"' form the value; the
  only escapes are \" (a quote) and \\ (a backslash). Scanning left to right, a backslash
  followed by any other character, or by nothing, is the error "bad escape" at the
  backslash's position; reaching the end of the query with no closing quote is the error
  "unterminated string" at the OPENING quote's position.
- WORD: a letter (A-Z, a-z) or '_', followed by a maximal run of letters, digits, '_'
  and '.'. The words and, or, not, in, has (exactly these lowercase spellings) are
  keywords; every other word is a FIELD name ("c.d" is the single field name "c.d").
- Any other character: error "unexpected character 'C'" at its position ('!' not
  followed by '=' is such a character).

STEP 2 — PARSING. Grammar (END is the end of the query, at position len(query)):

    query      := or_expr END
    or_expr    := and_expr { 'or' and_expr }
    and_expr   := not_expr { 'and' not_expr }
    not_expr   := 'not' not_expr | primary
    primary    := '(' or_expr ')'
                | 'has' FIELD
                | FIELD cmp_op literal
                | FIELD 'in' '[' literal { ',' literal } ']'
    literal    := INT | STRING

So `not` binds tighter than `and`, which binds tighter than `or`; `not a = 1 and b = 2`
is `(not (a = 1)) and (b = 2)`. If the tokens do not form a valid query, report the FIRST
token (leftmost) at which the tokens read so far, including that token, stop being the
beginning of some valid query (this is where a standard recursive-descent parser for the
grammar first fails), with message:
- "unexpected end of input"  if that token is END,
- "unexpected token 'T'"     otherwise, where T is the token's exact source text (for a
                             STRING including its quotes and backslashes as written).

STEP 3 — EVALUATION uses three truth values TRUE, FALSE, UNKNOWN:
- `FIELD op literal`: if the record has no such field -> UNKNOWN. If the field's value
  and the literal have different types (int vs str): '=' -> FALSE, '!=' -> TRUE, and
  '<' '<=' '>' '>=' -> UNKNOWN. Same type: the ordinary Python comparison (strings
  compare by code point) -> TRUE or FALSE.
- `FIELD in [l1, ..., lk]`: field missing -> UNKNOWN; otherwise TRUE if the value equals
  some li of the same type, else FALSE.
- `has FIELD`: TRUE if the record has the field, else FALSE (never UNKNOWN).
- not: TRUE<->FALSE, UNKNOWN stays UNKNOWN.
- and: FALSE if any operand is FALSE, else UNKNOWN if any is UNKNOWN, else TRUE.
- or:  TRUE if any operand is TRUE, else UNKNOWN if any is UNKNOWN, else FALSE.
A record is selected only when the whole query is TRUE.

Sizes: up to 5,000 records, queries up to 100,000 characters, len(records) * len(query)
at most 3 * 10**6, and parentheses or `not` chains nested up to 3,000 deep (mind
Python's default recursion limit of 1000). The function must finish in a few seconds.

Examples, with
    R = [{"age": 31, "city": "Lima"}, {"age": 17}, {"city": "Quito", "age": "40"}, {}]
- filter_records('age >= 18 or city = "Lima"', R) == ("ok", [0])
  # record 2: "40" >= 18 is UNKNOWN (str vs int); record 3: UNKNOWN or UNKNOWN
- filter_records("age != 31", R) == ("ok", [1, 2])
  # record 2: "40" != 31 is TRUE (different types); record 3: missing field -> UNKNOWN
- filter_records('not city in ["Lima"]', R) == ("ok", [2])
- filter_records("age > 20 and not age > 30 or has city", R) == ("ok", [0, 2])
- filter_records("age > 18 and city = Lima", R) == ("error", 20, "unexpected token 'Lima'")
- filter_records("age >= 18 or", R) == ("error", 12, "unexpected end of input")
- filter_records('name = "a\\q"', R) == ("error", 9, "bad escape")
  # the query text is  name = "a\q"
