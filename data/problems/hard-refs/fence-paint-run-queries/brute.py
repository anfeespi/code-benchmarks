def fence_report(colors, operations):
    fence = list(colors)
    out = []
    for op in operations:
        if op[0] == "paint":
            _, l, r, c = op
            for i in range(l, r + 1):
                fence[i] = c
        else:
            _, l, r = op
            # enumerate maximal runs explicitly
            runs = []
            i = l
            while i <= r:
                j = i
                while j + 1 <= r and fence[j + 1] == fence[i]:
                    j += 1
                runs.append(j - i + 1)
                i = j + 1
            out.append((len(runs), max(runs)))
    return out
