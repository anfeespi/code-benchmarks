import heapq
from collections import OrderedDict


def run_cache(capacity, ops):
    if not isinstance(capacity, int) or capacity < 1:
        raise ValueError("capacity must be a positive int")

    store = OrderedDict()  # key -> [value, expires_at or None, version]; oldest use first
    expiry = []            # (expires_at, version, key) for entries that can expire
    version = 0
    out = []
    last_t = None

    def purge(t):
        while expiry and expiry[0][0] <= t:
            _, ver, key = heapq.heappop(expiry)
            entry = store.get(key)
            if entry is not None and entry[2] == ver:
                del store[key]

    for op in ops:
        kind, t = op[0], op[1]
        if last_t is not None and t < last_t:
            raise ValueError("operations must have non-decreasing timestamps")
        last_t = t

        if kind == "put":
            _, _, key, value, ttl = op
            if ttl is not None and (not isinstance(ttl, int) or ttl < 1):
                raise ValueError("ttl must be None or a positive int")
            purge(t)
            expires_at = None if ttl is None else t + ttl
            version += 1
            if expires_at is not None:
                heapq.heappush(expiry, (expires_at, version, key))
            if key in store:
                store[key] = [value, expires_at, version]
                store.move_to_end(key)
                continue
            if len(store) >= capacity:
                store.popitem(last=False)
            store[key] = [value, expires_at, version]

        elif kind == "get":
            purge(t)
            key = op[2]
            entry = store.get(key)
            if entry is None:
                out.append(None)
            else:
                store.move_to_end(key)
                out.append(entry[0])

        elif kind == "size":
            purge(t)
            out.append(len(store))

        else:
            raise ValueError("unknown operation %r" % (kind,))

    return out
