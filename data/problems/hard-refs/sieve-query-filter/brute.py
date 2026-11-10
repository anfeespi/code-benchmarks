# Independent reference: regex lexer, Pratt parser, evaluation with True/False/None truth tables.
import re

TOKRE = re.compile(r'[ \t\n]+|(?P<op>!=|<=|>=|[=<>])|(?P<p>[()\[\],])|(?P<int>-?[0-9]+)|(?P<id>[A-Za-z_][A-Za-z0-9_.]*)')
KW = ("and", "or", "not", "in", "has")


class Bad(Exception):
    pass


def lex(q):
    out, i = [], 0
    while i < len(q):
        if q[i] == '"':
            m = re.compile(r'"((?:[^"\\]|\\["\\])*)"').match(q, i)
            if m:
                out.append(("lit", m.group(1).replace('\\\\', '\x00').replace('\\"', '"').replace('\x00', '\\'), i, m.group()))
                i = m.end()
                continue
            j = i + 1
            while j < len(q):
                if q[j] == "\\" and (j + 1 >= len(q) or q[j + 1] not in '"\\'):
                    raise Bad(("error", j, "bad escape"))
                j += 2 if q[j] == "\\" else 1
            raise Bad(("error", i, "unterminated string"))
        m = TOKRE.match(q, i)
        if not m:
            raise Bad(("error", i, "unexpected character '%s'" % q[i]))
        g = m.lastgroup
        if g == "op":
            out.append(("op", m.group(), i, m.group()))
        elif g == "p":
            out.append((m.group(), m.group(), i, m.group()))
        elif g == "int":
            out.append(("lit", int(m.group()), i, m.group()))
        elif g == "id":
            w = m.group()
            out.append((w if w in KW else "field", w, i, w))
        i = m.end()
    out.append(("end", None, len(q), ""))
    return out


def filter_records(query, records):
    try:
        toks = lex(query)
    except Bad as b:
        return b.args[0]
    k = [0]

    def peek():
        return toks[k[0]]

    def die():
        kind, _, pos, text = peek()
        raise Bad(("error", pos, "unexpected end of input" if kind == "end" else "unexpected token '%s'" % text))

    def need(kind):
        if peek()[0] != kind:
            die()
        k[0] += 1
        return toks[k[0] - 1]

    BP = {"or": 1, "and": 3}

    def expr(minbp):
        kind = peek()[0]
        if kind == "not":
            k[0] += 1
            left = ("NOT", expr(5))
        elif kind == "(":
            k[0] += 1
            left = expr(0)
            need(")")
        elif kind == "has":
            k[0] += 1
            left = ("HAS", need("field")[1])
        elif kind == "field":
            f = need("field")[1]
            if peek()[0] == "op":
                op = need("op")[1]
                left = ("CMP", f, op, need("lit")[1])
            elif peek()[0] == "in":
                k[0] += 1
                need("[")
                xs = [need("lit")[1]]
                while peek()[0] != "]":
                    need(",")
                    xs.append(need("lit")[1])
                need("]")
                left = ("IN", f, xs)
            else:
                die()
        else:
            die()
        while peek()[0] in BP and BP[peek()[0]] >= minbp:
            op = peek()[0]
            k[0] += 1
            left = (op.upper(), left, expr(BP[op] + 1))
        return left

    try:
        tree = expr(0)
        if peek()[0] != "end":
            die()
    except Bad as b:
        return b.args[0]

    def same(a, b):
        return isinstance(a, str) == isinstance(b, str)

    def ev(n, r):
        t = n[0]
        if t == "HAS":
            return n[1] in r
        if t == "CMP":
            _, f, op, lit = n
            if f not in r:
                return None
            v = r[f]
            if not same(v, lit):
                return {"=": False, "!=": True}.get(op)
            return {"=": v == lit, "!=": v != lit, "<": v < lit, "<=": v <= lit, ">": v > lit, ">=": v >= lit}[op]
        if t == "IN":
            if n[1] not in r:
                return None
            return any(same(r[n[1]], x) and r[n[1]] == x for x in n[2])
        if t == "NOT":
            v = ev(n[1], r)
            return None if v is None else not v
        a, b = ev(n[1], r), ev(n[2], r)
        if t == "AND":
            if a is False or b is False:
                return False
            return None if (a is None or b is None) else True
        if a is True or b is True:
            return True
        return None if (a is None or b is None) else False

    return ("ok", [i for i, r in enumerate(records) if ev(tree, r) is True])
