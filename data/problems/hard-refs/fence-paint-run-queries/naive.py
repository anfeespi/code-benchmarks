from itertools import groupby


def fence_report(colors, operations):
    # correct but O(n) per operation: slice-assign paints, rescan each queried range
    fence = list(colors)
    out = []
    for op in operations:
        if op[0] == "paint":
            _, l, r, c = op
            fence[l:r + 1] = [c] * (r - l + 1)
        else:
            _, l, r = op
            lens = [sum(1 for _ in g) for _, g in groupby(fence[l:r + 1])]
            out.append((len(lens), max(lens)))
    return out
