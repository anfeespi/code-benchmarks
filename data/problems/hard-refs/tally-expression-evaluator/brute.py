# Independent reference: char-class lexer + Pratt (binding-power) parser + tuple-AST evaluator.
import re

LEX = re.compile(r"(?P<sp> +)|(?P<int>[0-9]+)|(?P<name>[a-z_][a-z0-9_]*)|(?P<op><=|>=|==|!=|[-+*/%^()?:<>])")
CMPS = {"<", "<=", ">", ">=", "==", "!="}
LBP = {"?": 1, "<": 3, "<=": 3, ">": 3, ">=": 3, "==": 3, "!=": 3, "+": 5, "-": 5, "*": 7, "/": 7, "%": 7, "^": 11}


class Fail(Exception):
    pass


def lex(s):
    toks, i = [], 0
    while i < len(s):
        m = LEX.match(s, i)
        if not m:
            toks.append(("bad", s[i], i))
            i += 1
            continue
        if m.lastgroup != "sp":
            toks.append((m.lastgroup, m.group(), i))
        i = m.end()
    toks.append(("eof", "", len(s)))
    return toks


def evaluate(src, env):
    toks = lex(src)
    st = {"i": 0}

    def cur():
        return toks[st["i"]]

    def err_here():
        k, t, p = cur()
        msg = {"eof": "unexpected end of input", "bad": "unexpected character '%s'" % t}.get(k, "unexpected token '%s'" % t)
        raise Fail(("error", p, msg))

    def isop(t):
        return cur()[0] == "op" and cur()[1] == t

    def parse(min_bp):
        k, t, p = cur()
        if k == "int":
            st["i"] += 1
            left, was_cmp = ("lit", int(t)), False
        elif k == "name":
            st["i"] += 1
            left, was_cmp = ("var", t, p), False
        elif isop("("):
            st["i"] += 1
            left = parse(0)
            if not isop(")"):
                err_here()
            st["i"] += 1
            was_cmp = False
        elif isop("-"):
            st["i"] += 1
            left, was_cmp = ("neg", parse(9)), False
        else:
            err_here()
        while True:
            k, t, p = cur()
            if k != "op" or t not in LBP or LBP[t] < min_bp:
                return left
            if t in CMPS and was_cmp:
                err_here()
            st["i"] += 1
            if t == "?":
                mid = parse(0)
                if not isop(":"):
                    err_here()
                st["i"] += 1
                right = parse(1)
                left, was_cmp = ("tern", left, mid, right), False
            elif t == "^":
                left, was_cmp = ("bin", t, p, left, parse(9)), False
            elif t in CMPS:
                left, was_cmp = ("bin", t, p, left, parse(4)), True
            else:
                left, was_cmp = ("bin", t, p, left, parse(LBP[t] + 1)), False

    def ev(n):
        if n[0] == "lit":
            return n[1]
        if n[0] == "var":
            if n[1] in env:
                return env[n[1]]
            raise Fail(("error", n[2], "unknown name '%s'" % n[1]))
        if n[0] == "neg":
            return -ev(n[1])
        if n[0] == "tern":
            c = ev(n[1])
            return ev(n[2]) if c else ev(n[3])
        _, op, p, l, r = n
        x = ev(l)
        y = ev(r)
        if op in "/%":
            if y == 0:
                raise Fail(("error", p, "division by zero"))
            return x // y if op == "/" else x % y
        if op == "^":
            if y < 0:
                raise Fail(("error", p, "negative exponent"))
            if y > 256:
                raise Fail(("error", p, "exponent too large"))
            return x ** y
        if op == "+":
            return x + y
        if op == "-":
            return x - y
        if op == "*":
            return x * y
        return 1 if eval("x %s y" % op) else 0

    try:
        tree = parse(0)
        if cur()[0] != "eof":
            err_here()
        return ("ok", ev(tree))
    except Fail as f:
        return f.args[0]
