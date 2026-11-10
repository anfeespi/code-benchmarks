from collections import OrderedDict


def run_cache(capacity, ops):
    if not isinstance(capacity, int) or capacity < 1:
        raise ValueError("capacity must be a positive int")

    store = OrderedDict()  # key -> [value, expires_at or None]; oldest use first
    out = []
    last_t = None

    def alive(entry, t):
        return entry[1] is None or t <= entry[1]

    for op in ops:
        kind, t = op[0], op[1]
        if last_t is not None and t < last_t:
            raise ValueError("operations must have non-decreasing timestamps")
        last_t = t

        if kind == "put":
            _, _, key, value, ttl = op
            if ttl is not None and (not isinstance(ttl, int) or ttl < 1):
                raise ValueError("ttl must be None or a positive int")
            expires_at = None if ttl is None else t + ttl
            entry = store.get(key)
            if entry is not None and alive(entry, t):
                entry[0] = value
                entry[1] = expires_at
                continue
            store.pop(key, None)
            if len(store) >= capacity:
                # make room: drop whatever has already expired first
                for k in [k for k, e in store.items() if not alive(e, t)]:
                    del store[k]
                if len(store) >= capacity:
                    store.popitem(last=False)
            store[key] = [value, expires_at]

        elif kind == "get":
            key = op[2]
            entry = store.get(key)
            if entry is None:
                out.append(None)
            elif not alive(entry, t):
                del store[key]
                out.append(None)
            else:
                store.move_to_end(key)
                out.append(entry[0])

        elif kind == "size":
            out.append(len(store))

        else:
            raise ValueError("unknown operation %r" % (kind,))

    return out
