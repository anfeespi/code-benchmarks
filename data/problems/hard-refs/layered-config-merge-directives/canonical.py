import copy
import json
import re

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _child(path, name):
    if _IDENT.fullmatch(name):
        return path + "." + name
    return path + "[" + json.dumps(name, ensure_ascii=False) + "]"


def _cat(v):
    if isinstance(v, bool):
        return "bool"
    if v is None:
        return "null"
    for t, n in ((dict, "dict"), (list, "list"), (str, "str"), (int, "int"), (float, "float")):
        if isinstance(v, t):
            return n
    return type(v).__name__


def _merge_into(target, overlay, path, layer, warnings):
    for key, val in overlay.items():
        if not isinstance(key, str):
            raise TypeError("layer %d: non-string key at %s" % (layer, path))
        if key.startswith("-"):
            name = key[1:]
            if not name:
                raise ValueError("layer %d: empty key name at %s" % (layer, path))
            p = _child(path, name)
            if val is not None:
                raise ValueError("layer %d: delete directive needs null at %s" % (layer, p))
            if name in target:
                del target[name]
            else:
                warnings.append("layer %d: delete of missing key at %s" % (layer, p))
        elif key.endswith("+"):
            name = key[:-1]
            if not name:
                raise ValueError("layer %d: empty key name at %s" % (layer, path))
            p = _child(path, name)
            if not isinstance(val, list):
                raise ValueError("layer %d: append directive needs a list at %s" % (layer, p))
            if name not in target:
                target[name] = copy.deepcopy(val)
            elif isinstance(target[name], list):
                target[name].extend(copy.deepcopy(val))
            else:
                raise ValueError("layer %d: cannot append to %s at %s" % (layer, _cat(target[name]), p))
        else:
            if not key:
                raise ValueError("layer %d: empty key name at %s" % (layer, path))
            p = _child(path, key)
            if key in target and _cat(target[key]) != _cat(val):
                warnings.append("layer %d: type change at %s: %s -> %s" % (layer, p, _cat(target[key]), _cat(val)))
            if isinstance(val, dict):
                if not (key in target and isinstance(target[key], dict)):
                    target[key] = {}
                _merge_into(target[key], val, p, layer, warnings)
            else:
                target[key] = copy.deepcopy(val)


def merge_layers(layers):
    if not isinstance(layers, list):
        raise TypeError("layers must be a list")
    result, warnings = {}, []
    for i, layer in enumerate(layers):
        if not isinstance(layer, dict):
            raise TypeError("layer %d is not a dict" % i)
        _merge_into(result, layer, "$", i, warnings)
    return result, warnings
