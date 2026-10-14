Write a Python function:

    def parse_outline(text: str) -> tuple

that parses the indentation-based config format "Outline" into Python values. It never
raises: it returns `("ok", value)` on success or `("error", line_number, message)` for the
first error, where `line_number` is 1-based and `message` is one of the exact strings below.

LINES. Split `text` on "\n" (and only on "\n"; any other character, including "\r", is an
ordinary character). Line k of that split is line number k. For every line:
- If the line consists only of spaces and tabs (or is empty) it is BLANK and ignored.
- Let LEAD be the longest prefix of the line made of spaces and tabs, and REST the
  remainder. If REST starts with '#', the line is a COMMENT and ignored (whatever LEAD is).
- Every other line is a CONTENT line. Its INDENT is len(LEAD). There are no inline
  comments: a '#' anywhere else is ordinary text.

CONTENT LINE SYNTAX (checked first for each content line, in this order):
1. If LEAD contains a tab: error "tab in indentation".
2. ITEM line: REST == "-" or REST starts with "- ". Its TEXT is REST[2:] with spaces (' '
   only) stripped from both ends. If TEXT is empty the line is an ITEM OPENER, otherwise an
   ITEM with scalar TEXT. (List items never contain inline mappings: "- a: 1" is the
   string "a: 1".)
3. Otherwise a KEY line: REST must contain ':', and the part before the FIRST ':' must be a
   valid key: one char from [A-Za-z_] followed by zero or more chars from [A-Za-z0-9_-]
   (so no spaces). Let AFTER be the text after that ':'. If AFTER consists only of spaces
   (or is empty) the line is a KEY OPENER. Otherwise AFTER must start with a space, and the
   scalar TEXT is AFTER with spaces stripped from both ends. Anything else (no ':', invalid
   key, or a non-space right after the ':' as in "a:b") is the error "invalid entry".
4. Scalar TEXT conversion:
   - Starts with '"': a quoted string. Scan the characters after the opening quote left to
     right: a backslash must be followed by one of  \  "  n  t  (meaning backslash, quote,
     newline, tab); a backslash followed by anything else, or by nothing, is the error
     "bad escape". The first unescaped '"' closes the string and must be the LAST character
     of TEXT, otherwise "bad string"; reaching the end with no closing quote is also
     "bad string". The value is the unescaped content.
   - "true" -> True, "false" -> False, "null" -> None (exact, case-sensitive).
   - Matches  -?(0|[1-9][0-9]*)  (ASCII digits) -> int ("-0" is 0; "007" and "+3" are NOT
     ints).
   - Anything else -> the str TEXT itself.

STRUCTURE (checked for a content line only if its syntax is valid). The document is a
tree of blocks; a block is either a MAPPING (dict, made of KEY lines) or a LIST (list, made
of ITEM lines); all lines of one block have the same INDENT. An opener's value is a nested
block if one follows, else None.
- The first content line must have INDENT 0 (else "unexpected indent"); it starts the
  root block, whose kind (mapping or list) is the kind of that line.
- If the previous content line was an opener (KEY OPENER or ITEM OPENER) and this line's
  INDENT is strictly greater than the opener's INDENT, this line starts a NEW block (its
  kind is this line's kind, its indentation is this line's INDENT, any amount deeper) that
  becomes the opener's value. Children must be strictly deeper: unlike YAML, "- " items at
  the same indentation as their key are NOT children of it.
- Otherwise (the opener, if any, keeps the value None) the line must continue an open
  block: if its INDENT is greater than the INDENT of the innermost open block, error
  "unexpected indent"; if it is smaller, the deeper blocks are closed, and the INDENT
  must equal that of some enclosing open block, otherwise "inconsistent dedent". Then:
  if the line's kind differs from that block's kind, error "mixed block"; if it is a KEY
  line whose key already exists in that mapping, error "duplicate key 'KEY'".
- An opener at the end of the document has value None.

Lines are processed in order and the first error found is returned. Within one line the
checks happen in the order given above (tab, entry syntax, scalar conversion, then the
structure checks in the order listed). A document with no content lines returns
("ok", None). Inputs may have up to 250,000 lines and blocks nested up to 3,000 deep
(mind Python's default recursion limit of 1000); the function must run in a few seconds.

Examples:
    parse_outline('server:\n  host: example.org\n  ports:\n    - 80\n    - "443"\n    -\n'
                  '  limits:\n  debug: false\n# top-level comment\nname:   007  ')
      == ("ok", {"server": {"host": "example.org", "ports": [80, "443", None],
                            "limits": None, "debug": False},
                 "name": "007"})
    parse_outline("a:\n    b: 1\n  c: 2")  == ("error", 3, "inconsistent dedent")
    parse_outline("a: 1\n  b: 2")          == ("error", 2, "unexpected indent")
    parse_outline('a: 1\nb:\n  - x\n  y: 2\nc "oops"') == ("error", 4, "mixed block")
    parse_outline("k: v\nk: w")            == ("error", 2, "duplicate key 'k'")
    parse_outline("\n  # indented comment\n\t\n") == ("ok", None)
