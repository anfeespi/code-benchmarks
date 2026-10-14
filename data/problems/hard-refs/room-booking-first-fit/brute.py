def run_ops(ops):
    books = []  # unordered list of (s, e)
    out = []
    for op in ops:
        name = op[0]
        if name == "book":
            _, s, e = op
            if s >= e:
                out.append("INVALID")
            elif any(max(s, a) < min(e, b) for a, b in books):
                out.append("CONFLICT")
            else:
                books.append((s, e))
                out.append(True)
        elif name == "cancel":
            hit = [bk for bk in books if bk[0] == op[1]]
            if hit:
                books.remove(hit[0])
                out.append(hit[0][1] - hit[0][0])
            else:
                out.append(0)
        elif name == "first_fit":
            _, t, d = op
            x = t
            while True:
                clash = [b for a, b in books if max(x, a) < min(x + d, b)]
                if not clash:
                    break
                x = max(clash)
            out.append(x)
        elif name == "free_between":
            _, a, b = op
            if a >= b:
                out.append(0)
            else:
                busy = sum(max(0, min(b, e) - max(a, s)) for s, e in books)
                out.append(b - a - busy)
    return out
