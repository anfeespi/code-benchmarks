def count_records(levels, margin, queries):
    # correct but O(sum of query lengths): rescans every window
    out = []
    for l, r in queries:
        record = levels[l]
        count = 1
        for x in levels[l + 1:r + 1]:
            if x >= record + margin:
                record = x
                count += 1
        out.append(count)
    return out
