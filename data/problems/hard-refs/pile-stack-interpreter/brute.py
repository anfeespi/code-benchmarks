# Independent reference: regex tokenizer, counter-based structure check, recursive evaluator.
import re
import sys

BUILTIN = "dup drop swap over rot + - * / % < = if times while call dip".split()
INTRE = re.compile(r"-?[0-9]+\Z")


class Stop(Exception):
    pass


def run_pile(src, max_steps):
    # the language's whitespace is exactly space/tab/newline/CR; other whitespace chars are ordinary
    toks = []
    buf = ""
    for ch in src:
        if ch in " \t\n\r" or ch in "[]":
            if buf:
                toks.append(buf)
            buf = ""
            if ch in "[]":
                toks.append(ch)
        else:
            buf += ch
    if buf:
        toks.append(buf)

    opens, in_def, close = [], None, {}
    i = 0
    while i < len(toks):
        t = toks[i]
        if t == "[":
            opens.append(i)
        elif t == "]":
            if not opens:
                return ("error", i, "unmatched ]")
            close[opens.pop()] = i
        elif t == ":":
            if opens or in_def is not None:
                return ("error", i, "misplaced :")
            if i == len(toks) - 1:
                return ("error", i, "unclosed :")
            nm = toks[i + 1]
            if nm in ("[", "]", ";", ":") or INTRE.match(nm) or nm in BUILTIN:
                return ("error", i + 1, "bad name")
            in_def = i
            i += 1
        elif t == ";":
            if in_def is None or opens:
                return ("error", i, "unmatched ;")
            close[in_def] = i
            in_def = None
        i += 1
    pending = ([(opens[0], "[")] if opens else []) + ([(in_def, ":")] if in_def is not None else [])
    if pending:
        idx, kind = min(pending)
        return ("error", idx, "unclosed " + kind)

    stack, defs, cnt = [], {}, [0]

    def fail(i, m):
        raise Stop(("error", i, m))

    def run(a, b):
        i = a
        while i < b:
            t = toks[i]
            cnt[0] += 1
            if cnt[0] > max_steps:
                fail(i, "step limit exceeded")
            if t == "[":
                stack.append(("Q", i + 1, close[i]))
                i = close[i] + 1
                continue
            if t == ":":
                defs[toks[i + 1]] = (i + 2, close[i])
                i = close[i] + 1
                continue
            i += 1
            if INTRE.match(t):
                stack.append(int(t))
            elif t in BUILTIN:
                prim(t, i - 1)
            elif t in defs:
                run(*defs[t])
            else:
                fail(i - 1, "unknown word '%s'" % t)

    def isq(v):
        return isinstance(v, tuple)

    def prim(t, at):
        need = {"dup": 1, "drop": 1, "call": 1, "rot": 3, "if": 3}.get(t, 2)
        if len(stack) < need:
            fail(at, "stack underflow")
        args = stack[-need:]
        if t == "dup":
            stack.append(args[0])
        elif t == "drop":
            stack.pop()
        elif t == "swap":
            stack[-2:] = [args[1], args[0]]
        elif t == "over":
            stack.append(args[0])
        elif t == "rot":
            stack[-3:] = [args[1], args[2], args[0]]
        elif t in "+-*/%<=":
            x, y = args
            if isq(x) or isq(y):
                fail(at, "type error")
            if t in "/%" and y == 0:
                fail(at, "division by zero")
            del stack[-2:]
            stack.append({"+": lambda: x + y, "-": lambda: x - y, "*": lambda: x * y, "/": lambda: x // y,
                          "%": lambda: x % y, "<": lambda: int(x < y), "=": lambda: int(x == y)}[t]())
        elif t == "if":
            c, p, q = args
            if isq(c) or not isq(p) or not isq(q):
                fail(at, "type error")
            del stack[-3:]
            run(*(p if c else q)[1:])
        elif t == "times":
            q, n = args
            if not isq(q) or isq(n):
                fail(at, "type error")
            if n < 0:
                fail(at, "negative count")
            del stack[-2:]
            if q[1] == q[2]:
                return
            for _ in range(n):
                run(q[1], q[2])
        elif t == "while":
            c, body = args
            if not isq(c) or not isq(body):
                fail(at, "type error")
            del stack[-2:]
            while True:
                run(c[1], c[2])
                if not stack:
                    fail(at, "stack underflow")
                if isq(stack[-1]):
                    fail(at, "type error")
                if not stack.pop():
                    break
                run(body[1], body[2])
        elif t == "call":
            if not isq(args[0]):
                fail(at, "type error")
            stack.pop()
            run(args[0][1], args[0][2])
        elif t == "dip":
            a, q = args
            if not isq(q):
                fail(at, "type error")
            del stack[-2:]
            run(q[1], q[2])
            stack.append(a)

    def show(v):
        if not isq(v):
            return v
        out, i = [], v[1]
        while i < v[2]:
            if toks[i] == "[":
                out.append(show(("Q", i + 1, close[i])))
                i = close[i] + 1
            else:
                out.append(toks[i])
                i += 1
        return out

    old = sys.getrecursionlimit()
    sys.setrecursionlimit(20000)
    try:
        run(0, len(toks))
        return ("ok", [show(v) for v in stack])
    except Stop as s:
        return s.args[0]
    finally:
        sys.setrecursionlimit(old)
