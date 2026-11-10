_KEY_START = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_")
_KEY_REST = _KEY_START | set("0123456789-")
_ESC = {"\\": "\\", '"': '"', "n": "\n", "t": "\t"}


class _Err(Exception):
    pass


def _scalar(v):
    if v[0] == '"':
        out, i = [], 1
        while i < len(v):
            ch = v[i]
            if ch == "\\":
                if i + 1 >= len(v) or v[i + 1] not in _ESC:
                    raise _Err("bad escape")
                out.append(_ESC[v[i + 1]])
                i += 2
            elif ch == '"':
                if i != len(v) - 1:
                    raise _Err("bad string")
                return "".join(out)
            else:
                out.append(ch)
                i += 1
        raise _Err("bad string")
    if v == "true":
        return True
    if v == "false":
        return False
    if v == "null":
        return None
    d = v[1:] if v[0] == "-" else v
    if d and d.isascii() and d.isdigit() and (d == "0" or d[0] != "0"):
        return int(v)
    return v


def _classify(rest):
    """-> (kind, key, is_opener, value)"""
    if rest == "-" or rest.startswith("- "):
        text = rest[2:].strip(" ")
        if not text:
            return ("item", None, True, None)
        return ("item", None, False, _scalar(text))
    idx = rest.find(":")
    if idx <= 0:
        raise _Err("invalid entry")
    key = rest[:idx]
    if key[0] not in _KEY_START or any(ch not in _KEY_REST for ch in key):
        raise _Err("invalid entry")
    after = rest[idx + 1:]
    if after.strip(" ") == "":
        return ("key", key, True, None)
    if after[0] != " ":
        raise _Err("invalid entry")
    return ("key", key, False, _scalar(after.strip(" ")))


def parse_outline(text):
    root = None
    stack = []          # frames: [indent, container, kind]
    pending = None      # (opener indent, container, slot)
    for lineno, line in enumerate(text.split("\n"), 1):
        j = 0
        while j < len(line) and line[j] in " \t":
            j += 1
        rest = line[j:]
        if rest == "" or rest[0] == "#":
            continue
        lead = line[:j]
        try:
            if "\t" in lead:
                raise _Err("tab in indentation")
            indent = j
            kind, key, opener, value = _classify(rest)
            if root is None:
                if indent != 0:
                    raise _Err("unexpected indent")
                root = {} if kind == "key" else []
                stack.append([0, root, kind])
                frame = stack[-1]
            elif pending is not None and indent > pending[0]:
                child = {} if kind == "key" else []
                pending[1][pending[2]] = child
                stack.append([indent, child, kind])
                frame = stack[-1]
            else:
                if indent > stack[-1][0]:
                    raise _Err("unexpected indent")
                while stack[-1][0] > indent:
                    stack.pop()
                if stack[-1][0] != indent:
                    raise _Err("inconsistent dedent")
                frame = stack[-1]
                if frame[2] != kind:
                    raise _Err("mixed block")
                if kind == "key" and key in frame[1]:
                    raise _Err("duplicate key '%s'" % key)
            pending = None
            cont = frame[1]
            if kind == "key":
                cont[key] = value
                slot = key
            else:
                cont.append(value)
                slot = len(cont) - 1
            if opener:
                pending = (indent, cont, slot)
        except _Err as e:
            return ("error", lineno, e.args[0])
    return ("ok", root)
