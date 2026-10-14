import sys

_TWO = ("<=", ">=", "==", "!=")
_ONE = set("+-*/%^()?:<>")
_CMP = ("<", "<=", ">", ">=", "==", "!=")


class _Err(Exception):
    def __init__(self, pos, msg):
        self.pos, self.msg = pos, msg


def _tokens(src):
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == " ":
            i += 1
        elif c.isdigit() and c in "0123456789":
            j = i
            while j < n and src[j] in "0123456789":
                j += 1
            out.append(("int", src[i:j], i))
            i = j
        elif c == "_" or ("a" <= c <= "z"):
            j = i
            while j < n and (src[j] == "_" or "a" <= src[j] <= "z" or src[j] in "0123456789"):
                j += 1
            out.append(("name", src[i:j], i))
            i = j
        elif src[i:i + 2] in _TWO:
            out.append(("op", src[i:i + 2], i))
            i += 2
        elif c in _ONE:
            out.append(("op", c, i))
            i += 1
        else:
            out.append(("bad", c, i))
            i += 1
    out.append(("eof", "", n))
    return out


class _Parser:
    def __init__(self, toks):
        self.t, self.k = toks, 0

    def peek(self):
        return self.t[self.k]

    def fail(self):
        kind, text, pos = self.t[self.k]
        if kind == "eof":
            raise _Err(pos, "unexpected end of input")
        if kind == "bad":
            raise _Err(pos, "unexpected character '%s'" % text)
        raise _Err(pos, "unexpected token '%s'" % text)

    def is_op(self, *ops):
        kind, text, _ = self.t[self.k]
        return kind == "op" and text in ops

    def expect(self, op):
        if not self.is_op(op):
            self.fail()
        self.k += 1

    def cond(self):
        c = self.cmp()
        if self.is_op("?"):
            pos = self.peek()[2]
            self.k += 1
            a = self.cond()
            self.expect(":")
            b = self.cond()
            return ("?", pos, c, a, b)
        return c

    def cmp(self):
        left = self.sum()
        if self.is_op(*_CMP):
            _, op, pos = self.peek()
            self.k += 1
            right = self.sum()
            return (op, pos, left, right)
        return left

    def sum(self):
        left = self.term()
        while self.is_op("+", "-"):
            _, op, pos = self.peek()
            self.k += 1
            left = (op, pos, left, self.term())
        return left

    def term(self):
        left = self.unary()
        while self.is_op("*", "/", "%"):
            _, op, pos = self.peek()
            self.k += 1
            left = (op, pos, left, self.unary())
        return left

    def unary(self):
        if self.is_op("-"):
            pos = self.peek()[2]
            self.k += 1
            return ("neg", pos, self.unary())
        return self.power()

    def power(self):
        base = self.atom()
        if self.is_op("^"):
            pos = self.peek()[2]
            self.k += 1
            return ("^", pos, base, self.unary())
        return base

    def atom(self):
        kind, text, pos = self.peek()
        if kind == "int":
            self.k += 1
            return ("int", pos, int(text))
        if kind == "name":
            self.k += 1
            return ("name", pos, text)
        if self.is_op("("):
            self.k += 1
            e = self.cond()
            self.expect(")")
            return e
        self.fail()


def _eval(node, env):
    tag, pos = node[0], node[1]
    if tag == "int":
        return node[2]
    if tag == "name":
        if node[2] not in env:
            raise _Err(pos, "unknown name '%s'" % node[2])
        return env[node[2]]
    if tag == "neg":
        return -_eval(node[2], env)
    if tag == "?":
        return _eval(node[3], env) if _eval(node[2], env) != 0 else _eval(node[4], env)
    a = _eval(node[2], env)
    b = _eval(node[3], env)
    if tag == "+":
        return a + b
    if tag == "-":
        return a - b
    if tag == "*":
        return a * b
    if tag in ("/", "%"):
        if b == 0:
            raise _Err(pos, "division by zero")
        return a // b if tag == "/" else a % b
    if tag == "^":
        if b < 0:
            raise _Err(pos, "negative exponent")
        if b > 256:
            raise _Err(pos, "exponent too large")
        return a ** b
    return int({"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "==": a == b, "!=": a != b}[tag])


def evaluate(src, env):
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old, 1_000_000))
    try:
        p = _Parser(_tokens(src))
        tree = p.cond()
        if p.peek()[0] != "eof":
            p.fail()
        return ("ok", _eval(tree, env))
    except _Err as e:
        return ("error", e.pos, e.msg)
    finally:
        sys.setrecursionlimit(old)
