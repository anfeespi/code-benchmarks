def run_ops(ops):
    # every version is a full dict copy
    versions = [{}]
    out = []
    for op in ops:
        name, v = op[0], op[1]
        if not (isinstance(v, int) and not isinstance(v, bool) and 0 <= v < len(versions)):
            out.append("BADVER")
            continue
        d = versions[v]
        if name == "set":
            nd = dict(d)
            nd[op[2]] = op[3]
            versions.append(nd)
            out.append(len(versions) - 1)
        elif name == "del":
            if op[2] not in d:
                out.append("NOKEY")
            else:
                nd = dict(d)
                del nd[op[2]]
                versions.append(nd)
                out.append(len(versions) - 1)
        elif name == "get":
            out.append(d.get(op[2]))
        elif name == "count":
            out.append(sum(1 for k in d if op[2] <= k <= op[3]))
        elif name == "sum":
            out.append(sum(val for k, val in d.items() if op[2] <= k <= op[3]))
        elif name == "kth":
            ks = sorted(d)
            k = op[2]
            out.append(ks[k - 1] if 1 <= k <= len(ks) else None)
    return out
