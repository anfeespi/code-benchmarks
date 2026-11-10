This function replays a log of operations against a fixed-capacity cache that combines
least-recently-used eviction with a per-entry time-to-live. It passes the author's smoke
tests, but the numbers it produces on real logs disagree with the documented behaviour
below in several ways around expiry and eviction, and replaying long logs against a large
cache is far too slow. Find and fix the bug(s), returning a corrected version with the
exact same function name and signature (`run_cache(capacity, ops)`).

Current (buggy) implementation:

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

Contract:
- `capacity` must be an int >= 1, otherwise raise ValueError.
- `ops` is a list of tuples processed in list order. Each is one of:
    ("put", t, key, value, ttl)
    ("get", t, key)
    ("size", t)
  `t` is an int timestamp; timestamps must be non-decreasing along the list (equal values
  allowed), and an operation whose `t` is smaller than the previous operation's `t` raises
  ValueError. `ttl` is either None (the entry never expires) or an int >= 1; anything else
  raises ValueError. An unknown operation name raises ValueError. Keys are hashable,
  values are arbitrary objects. Errors are raised when the offending operation is reached.
- An entry written by a put at time `t` with an int `ttl` EXPIRES at `t + ttl`: at every
  time T >= t + ttl it no longer exists - it is not returned by get, not counted by size,
  and does not occupy capacity.
- ("put", t, key, value, ttl): if `key` currently exists (unexpired), replace its value and
  its expiry (recomputed from this put's `t` and `ttl`). Otherwise insert it; if the cache
  already holds `capacity` unexpired entries at that moment, first evict the least
  recently used unexpired entry. Every put counts as a USE of `key`.
- ("get", t, key): if `key` exists (unexpired) at time `t`, its value is the result and the
  get counts as a USE of `key`; otherwise the result is None.
- ("size", t): the result is the number of unexpired entries at time `t`.
- "Least recently used" compares the position in `ops` of each entry's most recent USE
  (operations sharing a timestamp are ordered by their list position).
- Return the list of results of the get and size operations, in order. Puts produce no
  result.

Performance: logs of 200,000 operations against capacities up to 100,000 must replay in
well under a few seconds.

Examples:
- run_cache(2, [("put", 0, "a", 1, 5), ("put", 1, "b", 2, None), ("get", 4, "a"),
                ("get", 5, "a"), ("size", 5)]) == [1, None, 1]
- run_cache(2, [("put", 0, "a", 1, None), ("put", 0, "b", 2, None), ("put", 1, "a", 10, None),
                ("put", 2, "c", 3, None), ("get", 2, "a"), ("get", 2, "b"), ("size", 3)])
    == [10, None, 2]
- run_cache(2, [("put", 0, "x", 1, 3), ("put", 1, "y", 2, None), ("put", 3, "z", 3, None),
                ("get", 3, "y"), ("size", 3)]) == [2, 2]
