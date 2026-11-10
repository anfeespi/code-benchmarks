def run_cache(capacity, ops):
    # Written from the contract alone: a flat list of entries, every rule evaluated by full scans.
    if not isinstance(capacity, int) or capacity < 1:
        raise ValueError("capacity must be a positive int")
    entries = []  # dicts: key, value, expires (None = never), used (last-use tick)
    tick = 0
    out = []
    prev = None
    for op in ops:
        kind, t = op[0], op[1]
        if prev is not None and t < prev:
            raise ValueError("operations must have non-decreasing timestamps")
        prev = t
        if kind not in ("put", "get", "size"):
            raise ValueError("unknown operation %r" % (kind,))
        if kind == "put":
            ttl = op[4]
            if ttl is not None and (not isinstance(ttl, int) or ttl < 1):
                raise ValueError("ttl must be None or a positive int")
        # an entry is visible at time t iff it never expires or t < expires
        entries = [e for e in entries if e["expires"] is None or t < e["expires"]]
        tick += 1
        if kind == "size":
            out.append(len(entries))
        elif kind == "get":
            hit = [e for e in entries if e["key"] == op[2]]
            if hit:
                hit[0]["used"] = tick
                out.append(hit[0]["value"])
            else:
                out.append(None)
        else:
            _, _, key, value, ttl = op
            exp = None if ttl is None else t + ttl
            hit = [e for e in entries if e["key"] == key]
            if hit:
                hit[0].update(value=value, expires=exp, used=tick)
            else:
                if len(entries) == capacity:
                    lru = min(entries, key=lambda e: e["used"])
                    entries.remove(lru)
                entries.append({"key": key, "value": value, "expires": exp, "used": tick})
    return out
