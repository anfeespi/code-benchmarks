This tokenizer for a small expression language is used by an editor plugin to underline
tokens and report syntax errors. Users report that some tokens are underlined in the wrong
place, that some valid inputs are rejected or split differently than the language
reference says, and that some invalid inputs are accepted or reported at the wrong
location. Find and fix the bug(s), returning a corrected version of the module with the
exact same entry point and signature (`tokenize(src)`); module-level helpers may stay.

Current (buggy) implementation:

TWO_CHAR_OPS = ("==", "!=", "<=", ">=")
ONE_CHAR_OPS = "<>=+-*/(),"
ESCAPES = {'"': '"', "\\": "\\", "n": "\n", "t": "\t"}


def _is_digit(ch):
    return "0" <= ch <= "9"


def _is_ident_start(ch):
    return ch == "_" or "a" <= ch <= "z" or "A" <= ch <= "Z"


def _is_ident_char(ch):
    return _is_ident_start(ch) or _is_digit(ch)


def tokenize(src):
    tokens = []
    n = len(src)
    i, line, col = 0, 1, 1

    def fail(at_line, at_col, message):
        raise ValueError("line %d col %d: %s" % (at_line, at_col, message))

    while i < n:
        ch = src[i]

        if ch == "\n":
            i += 1
            line += 1
            col = 1
            continue
        if ch == " " or ch == "\t":
            i += 1
            col += 1
            continue
        if ch == "#":
            end = src.find("\n", i)
            i = n if end == -1 else end + 1
            continue

        if _is_digit(ch):
            j = i
            while j < n and _is_digit(src[j]):
                j += 1
            is_float = False
            if j < n and src[j] == ".":
                j += 1
                while j < n and _is_digit(src[j]):
                    j += 1
                is_float = True
            if j < n and src[j] in "eE":
                j += 1
                if j < n and src[j] in "+-":
                    j += 1
                while j < n and _is_digit(src[j]):
                    j += 1
                is_float = True
            text = src[i:j]
            tokens.append(("NUMBER", float(text) if is_float else int(text), line, col))
            col += j - i
            i = j
            continue

        if _is_ident_start(ch):
            j = i
            while j < n and _is_ident_char(src[j]):
                j += 1
            tokens.append(("IDENT", src[i:j], line, col))
            col += j - i
            i = j
            continue

        if ch == '"':
            j = i + 1
            chars = []
            while True:
                if j >= n or src[j] == "\n":
                    fail(line, col + (j - i), "unterminated string")
                c = src[j]
                if c == '"':
                    j += 1
                    break
                if c == "\\":
                    if j + 1 >= n or src[j + 1] == "\n":
                        fail(line, col + (j - i), "unterminated string")
                    if src[j + 1] not in ESCAPES:
                        fail(line, col + (j - i), "bad escape")
                    chars.append(ESCAPES[src[j + 1]])
                    j += 2
                    continue
                chars.append(c)
                j += 1
            tokens.append(("STRING", "".join(chars), line, col))
            col += j - i
            i = j
            continue

        if src[i:i + 2] in TWO_CHAR_OPS:
            tokens.append(("OP", src[i:i + 2], line, col))
            i += 2
            col += 2
            continue
        if ch in ONE_CHAR_OPS:
            tokens.append(("OP", ch, line, col))
            i += 1
            col += 1
            continue

        fail(line, col, "unexpected character %r" % ch)

    return tokens

Language reference (this is the contract):
- `src` is a str. The result is a list of tuples `(kind, value, line, col)` in source
  order, where `line` and `col` are the 1-based line and column of the token's FIRST
  character. Lines are separated by "\n" only; every character (including a tab) is one
  column; the character after a "\n" is column 1 of the next line.
- Whitespace: " ", "\t" and "\n" separate tokens and produce nothing.
- Comments: "#" starts a comment that runs up to, but not including, the next "\n" (or to
  the end of the input). Comments produce nothing. A "#" inside a string literal is just
  a character of the string.
- NUMBER: one or more ASCII digits 0-9, optionally followed by a FRACTION, optionally
  followed by an EXPONENT, longest match. A FRACTION is "." followed by at least one
  digit; a "." not followed by a digit is not part of the number. An EXPONENT is "e" or
  "E", an optional "+" or "-", then at least one digit; if that full shape is not
  present, the "e"/"E" (and any sign) are not part of the number. `value` is int(lexeme)
  if the lexeme has neither fraction nor exponent, else float(lexeme). Leading zeros are
  allowed ("007" -> 7). No separator is required after a number ("12ab" is NUMBER 12
  followed by IDENT "ab").
- IDENT: an ASCII letter or "_" followed by any number of ASCII letters, digits or "_".
  `value` is the lexeme.
- STRING: a double quote, then characters, then a closing double quote. Inside, a
  backslash starts an escape: \" -> ", \\ -> \, \n -> newline, \t -> tab. `value` is the
  decoded text (without the quotes). A raw "\n" may not appear inside a string literal.
- OP: one of  ==  !=  <=  >=  ->  <  >  =  +  -  *  /  (  )  ,  matched longest-first
  (so "->" is one OP, "-->" is "-" then "->", and a lone "!" is not an operator).
- Errors: scanning is left to right, and the first problem reached raises ValueError
  with a message of exactly the form "line L col C: MESSAGE":
    * a character that cannot start any token: MESSAGE is "unexpected character " followed
      by repr() of the character (e.g. "line 1 col 3: unexpected character '@'"), at that
      character's position;
    * inside a string, a backslash followed by any character other than ", \, n or t:
      MESSAGE is "bad escape", at the position of the backslash;
    * a string literal that reaches a "\n" or the end of the input before its closing
      quote (including a backslash immediately followed by "\n" or by the end of the
      input): MESSAGE is "unterminated string", at the position of the OPENING quote.
- An empty or all-whitespace/comment input returns [].

Examples:
- tokenize('x = 3.5e-2 -> f("a\\tb", 7)') == [
      ("IDENT", "x", 1, 1), ("OP", "=", 1, 3), ("NUMBER", 0.035, 1, 5), ("OP", "->", 1, 12),
      ("IDENT", "f", 1, 15), ("OP", "(", 1, 16), ("STRING", "a\tb", 1, 17),
      ("OP", ",", 1, 23), ("NUMBER", 7, 1, 25), ("OP", ")", 1, 26)]
- tokenize("n == 2e # done\nm") == [("IDENT", "n", 1, 1), ("OP", "==", 1, 3),
      ("NUMBER", 2, 1, 6), ("IDENT", "e", 1, 7), ("IDENT", "m", 2, 1)]
- tokenize('say("hi\n)') raises ValueError("line 1 col 5: unterminated string")
