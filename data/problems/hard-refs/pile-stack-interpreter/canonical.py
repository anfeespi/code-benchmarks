import sys

_BUILTINS = {"dup", "drop", "swap", "over", "rot", "+", "-", "*", "/", "%", "<", "=",
             "if", "times", "while", "call", "dip"}
_ARITY = {"dup": 1, "drop": 1, "swap": 2, "over": 2, "rot": 3, "+": 2, "-": 2, "*": 2, "/": 2, "%": 2,
          "<": 2, "=": 2, "if": 3, "times": 2, "while": 2, "call": 1, "dip": 2}


class _Err(Exception):
    def __init__(self, idx, msg):
        self.idx, self.msg = idx, msg


class _Quote:
    __slots__ = ("start", "end")

    def __init__(self, start, end):
        self.start, self.end = start, end  # token range of the body (exclusive of brackets)


def _tokenize(src):
    toks, cur = [], []
    for ch in src:
        if ch in " \t\n\r":
            if cur:
                toks.append("".join(cur))
                cur = []
        elif ch in "[]":
            if cur:
                toks.append("".join(cur))
                cur = []
            toks.append(ch)
        else:
            cur.append(ch)
    if cur:
        toks.append("".join(cur))
    return toks


def _is_int(t):
    d = t[1:] if t.startswith("-") else t
    return d != "" and d.isascii() and d.isdigit()


def _structure(toks):
    match = {}
    stack = []
    i, n = 0, len(toks)
    while i < n:
        t = toks[i]
        if t == "[":
            stack.append(i)
        elif t == "]":
            if not stack or toks[stack[-1]] != "[":
                raise _Err(i, "unmatched ]")
            match[stack.pop()] = i
        elif t == ":":
            if stack:
                raise _Err(i, "misplaced :")
            if i + 1 >= n:
                raise _Err(i, "unclosed :")
            name = toks[i + 1]
            if name in ("[", "]", ":", ";") or _is_int(name) or name in _BUILTINS:
                raise _Err(i + 1, "bad name")
            stack.append(i)
            i += 1
        elif t == ";":
            if not stack or toks[stack[-1]] != ":":
                raise _Err(i, "unmatched ;")
            match[stack.pop()] = i
        i += 1
    if stack:
        raise _Err(stack[0], "unclosed " + toks[stack[0]])
    return match


def _render(v, toks, match):
    if isinstance(v, int):
        return v
    out, i = [], v.start
    while i < v.end:
        if toks[i] == "[":
            out.append(_render(_Quote(i + 1, match[i]), toks, match))
            i = match[i] + 1
        else:
            out.append(toks[i])
            i += 1
    return out


def run_pile(src, max_steps):
    toks = _tokenize(src)
    try:
        match = _structure(toks)
    except _Err as e:
        return ("error", e.idx, e.msg)
    words = {}
    stack = []
    steps = 0
    # frames: ["seq", pos, end] | ["times", quote, remaining] | ["while", cquote, bquote, idx] | ["push", value]
    frames = [["seq", 0, len(toks)]]
    try:
        while frames:
            fr = frames[-1]
            kind = fr[0]
            if kind == "seq":
                pos = fr[1]
                if pos >= fr[2]:
                    frames.pop()
                    continue
                t = toks[pos]
                steps += 1
                if steps > max_steps:
                    raise _Err(pos, "step limit exceeded")
                if t == "[":
                    fr[1] = match[pos] + 1
                    stack.append(_Quote(pos + 1, match[pos]))
                    continue
                if t == ":":
                    fr[1] = match[pos] + 1
                    words[toks[pos + 1]] = (pos + 2, match[pos])
                    continue
                fr[1] = pos + 1
                if _is_int(t):
                    stack.append(int(t))
                    continue
                if t in _BUILTINS:
                    if len(stack) < _ARITY[t]:
                        raise _Err(pos, "stack underflow")
                    if t == "dup":
                        stack.append(stack[-1])
                    elif t == "drop":
                        stack.pop()
                    elif t == "swap":
                        stack[-1], stack[-2] = stack[-2], stack[-1]
                    elif t == "over":
                        stack.append(stack[-2])
                    elif t == "rot":
                        stack.append(stack.pop(-3))
                    elif t in ("+", "-", "*", "/", "%", "<", "="):
                        a, b = stack[-2], stack[-1]
                        if not (isinstance(a, int) and isinstance(b, int)):
                            raise _Err(pos, "type error")
                        if t in "/%" and b == 0:
                            raise _Err(pos, "division by zero")
                        del stack[-2:]
                        if t == "+":
                            stack.append(a + b)
                        elif t == "-":
                            stack.append(a - b)
                        elif t == "*":
                            stack.append(a * b)
                        elif t == "/":
                            stack.append(a // b)
                        elif t == "%":
                            stack.append(a % b)
                        elif t == "<":
                            stack.append(1 if a < b else 0)
                        else:
                            stack.append(1 if a == b else 0)
                    elif t == "if":
                        c, x, y = stack[-3], stack[-2], stack[-1]
                        if not (isinstance(c, int) and isinstance(x, _Quote) and isinstance(y, _Quote)):
                            raise _Err(pos, "type error")
                        del stack[-3:]
                        q = x if c != 0 else y
                        frames.append(["seq", q.start, q.end])
                    elif t == "times":
                        q, k = stack[-2], stack[-1]
                        if not (isinstance(q, _Quote) and isinstance(k, int)):
                            raise _Err(pos, "type error")
                        if k < 0:
                            raise _Err(pos, "negative count")
                        del stack[-2:]
                        if q.start < q.end and k > 0:
                            frames.append(["times", q, k])
                    elif t == "while":
                        c, b = stack[-2], stack[-1]
                        if not (isinstance(c, _Quote) and isinstance(b, _Quote)):
                            raise _Err(pos, "type error")
                        del stack[-2:]
                        frames.append(["while", c, b, pos])
                        frames.append(["seq", c.start, c.end])
                    elif t == "call":
                        q = stack[-1]
                        if not isinstance(q, _Quote):
                            raise _Err(pos, "type error")
                        stack.pop()
                        frames.append(["seq", q.start, q.end])
                    elif t == "dip":
                        a, q = stack[-2], stack[-1]
                        if not isinstance(q, _Quote):
                            raise _Err(pos, "type error")
                        del stack[-2:]
                        frames.append(["push", a])
                        frames.append(["seq", q.start, q.end])
                    continue
                if t in words:
                    s, e = words[t]
                    frames.append(["seq", s, e])
                    continue
                raise _Err(pos, "unknown word '%s'" % t)
            elif kind == "times":
                if fr[2] == 0:
                    frames.pop()
                    continue
                fr[2] -= 1
                frames.append(["seq", fr[1].start, fr[1].end])
            elif kind == "while":
                # the condition quotation has just finished
                if not stack:
                    raise _Err(fr[3], "stack underflow")
                v = stack[-1]
                if not isinstance(v, int):
                    raise _Err(fr[3], "type error")
                stack.pop()
                if v != 0:
                    # run the body, then the condition again; this frame stays below both
                    frames.append(["seq", fr[1].start, fr[1].end])
                    frames.append(["seq", fr[2].start, fr[2].end])
                else:
                    frames.pop()
            else:  # push
                frames.pop()
                stack.append(fr[1])
    except _Err as e:
        return ("error", e.idx, e.msg)
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old, 200000))
    try:
        return ("ok", [_render(v, toks, match) for v in stack])
    finally:
        sys.setrecursionlimit(old)
