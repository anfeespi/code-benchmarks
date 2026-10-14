def run_ops(ops):
    # correct for any coordinates, but rebuilds the whole run list on every update: O(runs) per op
    runs = []  # sorted disjoint (l, r, label), merged
    out = []

    def rebuild(l, r, lab):
        changed = covered = 0
        new = []
        for (a, b, x) in runs:
            if b <= l or a >= r:
                new.append((a, b, x))
                continue
            ov = min(b, r) - max(a, l)
            covered += ov
            if x == lab:
                changed -= ov
            if a < l:
                new.append((a, l, x))
            if b > r:
                new.append((r, b, x))
        if lab is not None:
            new.append((l, r, lab))
            changed += r - l
        new.sort()
        merged = []
        for t in new:
            if merged and merged[-1][1] == t[0] and merged[-1][2] == t[2]:
                merged[-1] = (merged[-1][0], t[1], t[2])
            else:
                merged.append(t)
        runs[:] = merged
        return changed, covered

    for op in ops:
        name = op[0]
        if name == "paint":
            _, l, r, lab = op
            out.append(rebuild(l, r, lab)[0] if l < r else 0)
        elif name == "erase":
            _, l, r = op
            out.append(rebuild(l, r, None)[1] if l < r else 0)
        elif name == "at":
            p = op[1]
            out.append(next((x for a, b, x in runs if a <= p < b), None))
        elif name == "runs":
            out.append(len(runs))
        elif name == "total":
            out.append(sum(b - a for a, b, x in runs if x == op[1]))
        elif name == "next_change":
            p = op[1]
            ans = None
            for a, b, x in runs:
                if a <= p < b:
                    ans = b
                    break
                if a > p:
                    ans = a
                    break
            out.append(ans)
    return out
