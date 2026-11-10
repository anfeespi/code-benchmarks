def run_ops(ops):
    # cell-by-cell model; only usable for small coordinates
    cell = {}
    out = []
    for op in ops:
        name = op[0]
        if name == "paint":
            _, l, r, lab = op
            ch = 0
            for p in range(l, r):
                if cell.get(p) != lab:
                    ch += 1
                cell[p] = lab
            out.append(ch)
        elif name == "erase":
            _, l, r = op
            ch = 0
            for p in range(l, r):
                if p in cell:
                    ch += 1
                    del cell[p]
            out.append(ch)
        elif name == "at":
            out.append(cell.get(op[1]))
        elif name == "runs":
            ps = sorted(cell)
            runs = 0
            for idx, p in enumerate(ps):
                if idx == 0 or ps[idx - 1] != p - 1 or cell[ps[idx - 1]] != cell[p]:
                    runs += 1
            out.append(runs)
        elif name == "total":
            out.append(sum(1 for v in cell.values() if v == op[1]))
        elif name == "next_change":
            p = op[1]
            here = cell.get(p)
            hi = max(cell) + 1 if cell else p
            ans = None
            q = p + 1
            while q <= hi:
                if cell.get(q) != here:
                    ans = q
                    break
                q += 1
            out.append(ans)
    return out
