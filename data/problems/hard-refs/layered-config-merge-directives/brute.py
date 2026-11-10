import json

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_"


def _fmt_path(names):
    out = "$"
    for n in names:
        plain = len(n) > 0 and n[0] in LETTERS and all(c in LETTERS or c in "0123456789" for c in n)
        out += ("." + n) if plain else ("[" + json.dumps(n, ensure_ascii=False) + "]")
    return out


def _kind(v):
    if v is None:
        return "null"
    if v is True or v is False:
        return "bool"
    return {dict: "dict", list: "list", str: "str", int: "int", float: "float"}.get(type(v), type(v).__name__)


def _clone(v):
    if type(v) is dict:
        return {k: _clone(x) for k, x in v.items()}
    if type(v) is list:
        return [_clone(x) for x in v]
    return v


class _Fail(Exception):
    pass


def _apply(base, over, names, li, warns):
    """Return a NEW dict = base (a dict) with overlay `over` applied."""
    cur = list(base.items())  # ordered association list

    def find(name):
        for idx, (k, _) in enumerate(cur):
            if k == name:
                return idx
        return -1

    for key in over:
        val = over[key]
        if type(key) is not str:
            raise TypeError(f"layer {li}: non-string key at {_fmt_path(names)}")
        mode, name = "set", key
        if key[:1] == "-":
            mode, name = "del", key[1:]
        elif key[-1:] == "+":
            mode, name = "add", key[:-1]
        if name == "":
            raise ValueError(f"layer {li}: empty key name at {_fmt_path(names)}")
        here = _fmt_path(names + [name])
        idx = find(name)
        if mode == "del":
            if val is not None:
                raise ValueError(f"layer {li}: delete directive needs null at {here}")
            if idx < 0:
                warns.append(f"layer {li}: delete of missing key at {here}")
            else:
                cur.pop(idx)
        elif mode == "add":
            if type(val) is not list:
                raise ValueError(f"layer {li}: append directive needs a list at {here}")
            if idx < 0:
                cur.append((name, _clone(val)))
            elif type(cur[idx][1]) is list:
                cur[idx] = (name, cur[idx][1] + _clone(val))
            else:
                raise ValueError(f"layer {li}: cannot append to {_kind(cur[idx][1])} at {here}")
        else:
            old = cur[idx][1] if idx >= 0 else None
            if idx >= 0 and _kind(old) != _kind(val):
                warns.append(f"layer {li}: type change at {here}: {_kind(old)} -> {_kind(val)}")
            if type(val) is dict:
                start = old if (idx >= 0 and type(old) is dict) else {}
                new = _apply(start, val, names + [name], li, warns)
            else:
                new = _clone(val)
            if idx >= 0:
                cur[idx] = (name, new)
            else:
                cur.append((name, new))
    return dict(cur)


def merge_layers(layers):
    if type(layers) is not list:
        raise TypeError("layers must be a list")
    acc = {}
    warns = []
    for li in range(len(layers)):
        if type(layers[li]) is not dict:
            raise TypeError(f"layer {li} is not a dict")
        acc = _apply(acc, layers[li], [], li, warns)
    return (acc, warns)
