import sys

_KEYWORDS = {"and", "or", "not", "in", "has"}
_F, _U, _T = 0, 1, 2
_ID0 = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_")
_ID1 = _ID0 | set("0123456789.")
_DIG = set("0123456789")


class _Err(Exception):
    def __init__(self, pos, msg):
        self.pos, self.msg = pos, msg


def _lex(q):
    toks, i, n = [], 0, len(q)
    while i < n:
        c = q[i]
        if c in " \t\n":
            i += 1
        elif c in "()[],=<>!":
            two = q[i:i + 2]
            if two in ("!=", "<=", ">="):
                toks.append(("op", two, i, two))
                i += 2
            elif c == "!":
                raise _Err(i, "unexpected character '!'")
            else:
                toks.append(("op" if c in "=<>" else c, c, i, c))
                i += 1
        elif c in _DIG or (c == "-" and i + 1 < n and q[i + 1] in _DIG):
            j = i + 1
            while j < n and q[j] in _DIG:
                j += 1
            toks.append(("lit", int(q[i:j]), i, q[i:j]))
            i = j
        elif c == '"':
            j, out = i + 1, []
            while True:
                if j >= n:
                    raise _Err(i, "unterminated string")
                if q[j] == "\\":
                    if j + 1 < n and q[j + 1] in '"\\':
                        out.append(q[j + 1])
                        j += 2
                        continue
                    raise _Err(j, "bad escape")
                if q[j] == '"':
                    break
                out.append(q[j])
                j += 1
            toks.append(("lit", "".join(out), i, q[i:j + 1]))
            i = j + 1
        elif c in _ID0:
            j = i + 1
            while j < n and q[j] in _ID1:
                j += 1
            w = q[i:j]
            toks.append((w if w in _KEYWORDS else "field", w, i, w))
            i = j
        else:
            raise _Err(i, "unexpected character '%s'" % c)
    toks.append(("end", None, n, ""))
    return toks


class _P:
    def __init__(self, toks):
        self.t, self.k = toks, 0

    def fail(self):
        kind, _, pos, text = self.t[self.k]
        if kind == "end":
            raise _Err(pos, "unexpected end of input")
        raise _Err(pos, "unexpected token '%s'" % text)

    def kind(self):
        return self.t[self.k][0]

    def eat(self, kind):
        if self.kind() != kind:
            self.fail()
        tok = self.t[self.k]
        self.k += 1
        return tok

    def orexpr(self):
        parts = [self.andexpr()]
        while self.kind() == "or":
            self.k += 1
            parts.append(self.andexpr())
        return parts[0] if len(parts) == 1 else ("or", parts)

    def andexpr(self):
        parts = [self.notexpr()]
        while self.kind() == "and":
            self.k += 1
            parts.append(self.notexpr())
        return parts[0] if len(parts) == 1 else ("and", parts)

    def notexpr(self):
        count = 0
        while self.kind() == "not":
            self.k += 1
            count += 1
        node = self.primary()
        return ("not", node) if count % 2 else (("notnot", node) if count else node)

    def primary(self):
        kind = self.kind()
        if kind == "(":
            self.k += 1
            node = self.orexpr()
            self.eat(")")
            return node
        if kind == "has":
            self.k += 1
            return ("has", self.eat("field")[1])
        if kind == "field":
            name = self.t[self.k][1]
            self.k += 1
            if self.kind() == "op":
                op = self.t[self.k][1]
                self.k += 1
                return ("cmp", name, op, self.eat("lit")[1])
            if self.kind() == "in":
                self.k += 1
                self.eat("[")
                vals = [self.eat("lit")[1]]
                while self.kind() == ",":
                    self.k += 1
                    vals.append(self.eat("lit")[1])
                self.eat("]")
                return ("in", name, vals)
            self.fail()
        self.fail()


def _ev(node, rec):
    tag = node[0]
    if tag == "cmp":
        _, name, op, lit = node
        if name not in rec:
            return _U
        v = rec[name]
        if type(v) is not type(lit):
            return _F if op == "=" else (_T if op == "!=" else _U)
        if op == "=":
            r = v == lit
        elif op == "!=":
            r = v != lit
        elif op == "<":
            r = v < lit
        elif op == "<=":
            r = v <= lit
        elif op == ">":
            r = v > lit
        else:
            r = v >= lit
        return _T if r else _F
    if tag == "in":
        if node[1] not in rec:
            return _U
        v = rec[node[1]]
        return _T if any(type(v) is type(x) and v == x for x in node[2]) else _F
    if tag == "has":
        return _T if node[1] in rec else _F
    if tag == "not":
        return 2 - _ev(node[1], rec)
    if tag == "notnot":
        return _ev(node[1], rec)
    if tag == "and":
        r = _T
        for p in node[1]:
            r = min(r, _ev(p, rec))
            if r == _F:
                break
        return r
    r = _F
    for p in node[1]:
        r = max(r, _ev(p, rec))
        if r == _T:
            break
    return r


def filter_records(query, records):
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old, 100000))
    try:
        p = _P(_lex(query))
        tree = p.orexpr()
        if p.kind() != "end":
            p.fail()
        return ("ok", [i for i, rec in enumerate(records) if _ev(tree, rec) == _T])
    except _Err as e:
        return ("error", e.pos, e.msg)
    finally:
        sys.setrecursionlimit(old)
