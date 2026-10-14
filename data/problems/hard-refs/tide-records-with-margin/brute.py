def count_records(levels, margin, queries):
    out = []
    for l, r in queries:
        record = levels[l]
        count = 1
        for i in range(l + 1, r + 1):
            if levels[i] >= record + margin:
                record = levels[i]
                count += 1
        out.append(count)
    return out
