# Independent reference: regex line classifier (all lines first), then a recursive
# block builder over the records that precede the first syntax error.
import re

LINE_IGNORED = re.compile(r"^[ \t]*(#.*)?$", re.S)
KEY_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(.*)$", re.S)
INT = re.compile(r"^-?(0|[1-9][0-9]*)$")
QUOTED_OK = re.compile(r'^"((?:[^"\\]|\\[\\"nt])*)"$', re.S)


class E(Exception):
    def __init__(self, line, msg):
        self.line, self.msg = line, msg


def conv(v, ln):
    if v.startswith('"'):
        m = QUOTED_OK.match(v)
        if m:
            return re.sub(r'\\(.)', lambda g: {"n": "\n", "t": "\t"}.get(g.group(1), g.group(1)), m.group(1))
        # locate the first problem scanning from the left
        k = 1
        while k < len(v):
            if v[k] == "\\":
                if k + 1 < len(v) and v[k + 1] in '\\"nt':
                    k += 2
                    continue
                raise E(ln, "bad escape")
            if v[k] == '"':
                raise E(ln, "bad string")
            k += 1
        raise E(ln, "bad string")
    if v in ("true", "false", "null"):
        return {"true": True, "false": False, "null": None}[v]
    if INT.match(v):
        return int(v)
    return v


def records(text):
    recs = []
    for ln, line in enumerate(text.split("\n"), 1):
        if LINE_IGNORED.match(line):
            continue
        body = line.lstrip(" \t")
        lead = line[: len(line) - len(body)]
        if "\t" in lead:
            raise E(ln, "tab in indentation")
        ind = len(lead)
        if body == "-" or body[:2] == "- ":
            v = body[2:].strip(" ")
            recs.append((ln, ind, "L", None, v == "", None if v == "" else conv(v, ln)))
            continue
        m = KEY_LINE.match(body)
        if not m:
            raise E(ln, "invalid entry")
        tail = m.group(2)
        if tail.strip(" ") == "":
            recs.append((ln, ind, "M", m.group(1), True, None))
        elif not tail.startswith(" "):
            raise E(ln, "invalid entry")
        else:
            recs.append((ln, ind, "M", m.group(1), False, conv(tail.strip(" "), ln)))
    return recs


def parse_outline(text):
    recs, syntax_err = [], None
    # collect records line by line until the first syntax error
    lines = text.split("\n")
    for ln0 in range(len(lines)):
        try:
            r = records(lines[ln0])
        except E as e:
            syntax_err = E(ln0 + 1, e.msg)
            break
        recs += [(ln0 + 1,) + x[1:] for x in r]
    if not recs:
        if syntax_err:
            return ("error", syntax_err.line, syntax_err.msg)
        return ("ok", None)
    try:
        if recs[0][1] != 0:
            raise E(recs[0][0], "unexpected indent")
        st = {"i": 0}

        def block(level):
            kind = recs[st["i"]][2]
            cont = {} if kind == "M" else []
            returned_child = False
            while st["i"] < len(recs):
                ln, ind, k, key, opener, val = recs[st["i"]]
                if ind < level:
                    break
                if ind > level:
                    raise E(ln, "inconsistent dedent" if returned_child else "unexpected indent")
                returned_child = False
                if k != kind:
                    raise E(ln, "mixed block")
                if k == "M" and key in cont:
                    raise E(ln, "duplicate key '%s'" % key)
                st["i"] += 1
                if opener and st["i"] < len(recs) and recs[st["i"]][1] > level:
                    val = block(recs[st["i"]][1])
                    returned_child = True
                if k == "M":
                    cont[key] = val
                else:
                    cont.append(val)
            return cont

        root = block(0)
    except E as e:
        return ("error", e.line, e.msg)
    if syntax_err:
        return ("error", syntax_err.line, syntax_err.msg)
    return ("ok", root)
