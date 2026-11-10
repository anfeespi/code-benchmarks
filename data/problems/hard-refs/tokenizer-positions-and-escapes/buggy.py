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
