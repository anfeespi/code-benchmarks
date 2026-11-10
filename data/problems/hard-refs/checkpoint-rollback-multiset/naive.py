def run_ops(ops):
    # full snapshots per checkpoint; explicit set of valid ids
    items = []
    snaps = {}
    valid = set()
    next_id = 1
    out = []
    for op in ops:
        name = op[0]
        if name == "add":
            items.append(op[1])
            out.append(len(items))
        elif name == "remove":
            if op[1] in items:
                items.remove(op[1])
                out.append(True)
            else:
                out.append(False)
        elif name == "checkpoint":
            snaps[next_id] = list(items)
            valid.add(next_id)
            out.append(next_id)
            next_id += 1
        elif name == "rollback":
            c = op[1]
            if c not in valid:
                out.append("BADCP")
                continue
            items = list(snaps[c])
            valid = {x for x in valid if x <= c}
            out.append(len(items))
        elif name == "median":
            s = sorted(items)
            out.append(s[(len(s) + 1) // 2 - 1] if s else None)
        elif name == "count_less":
            out.append(sum(1 for x in items if x < op[1]))
        elif name == "distinct":
            out.append(len(set(items)))
    return out
