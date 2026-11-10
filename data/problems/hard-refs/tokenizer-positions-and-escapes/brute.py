import re

# Written from the contract alone: regex lexemes, positions recomputed from the absolute index.
_NUM = re.compile(r"[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_OPS = sorted(["==", "!=", "<=", ">=", "->", "<", ">", "=", "+", "-", "*", "/", "(", ")", ","], key=len, reverse=True)
_ESC = {'"': '"', "\\": "\\", "n": "\n", "t": "\t"}


def _where(src, idx):
    line = src.count("\n", 0, idx) + 1
    col = idx - (src.rfind("\n", 0, idx) + 1) + 1
    return line, col


def _err(src, idx, msg):
    line, col = _where(src, idx)
    raise ValueError("line %d col %d: %s" % (line, col, msg))


def tokenize(src):
    out = []
    i = 0
    while i < len(src):
        ch = src[i]
        if ch in " \t\n":
            i += 1
            continue
        if ch == "#":
            j = src.find("\n", i)
            i = len(src) if j < 0 else j
            continue
        m = _NUM.match(src, i)
        if m:
            lex = m.group()
            val = float(lex) if (m.group(1) or m.group(2)) else int(lex)
            out.append(("NUMBER", val) + _where(src, i))
            i = m.end()
            continue
        m = _IDENT.match(src, i)
        if m:
            out.append(("IDENT", m.group()) + _where(src, i))
            i = m.end()
            continue
        if ch == '"':
            j = i + 1
            buf = ""
            while True:
                if j >= len(src) or src[j] == "\n":
                    _err(src, i, "unterminated string")
                if src[j] == '"':
                    break
                if src[j] == "\\":
                    nxt = src[j + 1] if j + 1 < len(src) else None
                    if nxt is None or nxt == "\n":
                        _err(src, i, "unterminated string")
                    if nxt not in _ESC:
                        _err(src, j, "bad escape")
                    buf += _ESC[nxt]
                    j += 2
                    continue
                buf += src[j]
                j += 1
            out.append(("STRING", buf) + _where(src, i))
            i = j + 1
            continue
        for op in _OPS:
            if src.startswith(op, i):
                out.append(("OP", op) + _where(src, i))
                i += len(op)
                break
        else:
            _err(src, i, "unexpected character %r" % ch)
    return out
