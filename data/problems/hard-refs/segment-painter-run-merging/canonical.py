from bisect import bisect_left, bisect_right


def run_ops(ops):
    starts, ends, labs = [], [], []  # disjoint, sorted, maximal (merged) runs
    totals = {}
    out = []

    def merge_range(a, b):
        k = max(a, 1)
        while k < min(b, len(starts)):
            if ends[k - 1] == starts[k] and labs[k - 1] == labs[k]:
                ends[k - 1] = ends[k]
                del starts[k], ends[k], labs[k]
                b -= 1
            else:
                k += 1

    def cover(l, r, lab):
        # lab None = erase; returns (overlap with any label, overlap with same label)
        i = bisect_right(ends, l)
        j = bisect_left(starts, r)
        covered = same = 0
        for k in range(i, j):
            ov = min(ends[k], r) - max(starts[k], l)
            covered += ov
            totals[labs[k]] -= ov
            if labs[k] == lab:
                same += ov
        pieces = []
        if i < j and starts[i] < l:
            pieces.append((starts[i], l, labs[i]))
        if lab is not None:
            pieces.append((l, r, lab))
            totals[lab] = totals.get(lab, 0) + (r - l)
        if i < j and ends[j - 1] > r:
            pieces.append((r, ends[j - 1], labs[j - 1]))
        starts[i:j] = [p[0] for p in pieces]
        ends[i:j] = [p[1] for p in pieces]
        labs[i:j] = [p[2] for p in pieces]
        merge_range(i, i + len(pieces) + 1)
        return covered, same

    for op in ops:
        name = op[0]
        if name == "paint":
            _, l, r, lab = op
            if l >= r:
                out.append(0)
                continue
            covered, same = cover(l, r, lab)
            out.append((r - l) - same)
        elif name == "erase":
            _, l, r = op
            if l >= r:
                out.append(0)
                continue
            covered, _ = cover(l, r, None)
            out.append(covered)
        elif name == "at":
            p = op[1]
            k = bisect_right(starts, p) - 1
            out.append(labs[k] if k >= 0 and ends[k] > p else None)
        elif name == "runs":
            out.append(len(starts))
        elif name == "total":
            out.append(totals.get(op[1], 0))
        elif name == "next_change":
            p = op[1]
            k = bisect_right(starts, p) - 1
            if k >= 0 and ends[k] > p:
                out.append(ends[k])
            else:
                out.append(starts[k + 1] if k + 1 < len(starts) else None)
    return out
