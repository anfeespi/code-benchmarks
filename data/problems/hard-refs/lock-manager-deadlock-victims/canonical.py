def run_lock_manager(ops):
    holders = {}   # res -> {tx: mode}
    queues = {}    # res -> list of [tx, mode, is_upgrade]
    held = {}      # tx -> set of res
    waiting = {}   # tx -> res it is queued on
    finished = set()
    log = []

    def compatible(mode, res, me):
        for h, m in holders.get(res, {}).items():
            if h != me and (mode == "X" or m == "X"):
                return False
        return True

    def process_queue(i, res):
        q = queues.get(res)
        while q:
            tx, mode, _ = q[0]
            if not compatible(mode, res, tx):
                break
            q.pop(0)
            holders.setdefault(res, {})[tx] = mode
            held.setdefault(tx, set()).add(res)
            del waiting[tx]
            log.append(("GRANT", i, tx, res, mode))

    def release(i, tx):
        affected = set()
        r = waiting.pop(tx, None)
        if r is not None:
            queues[r] = [e for e in queues[r] if e[0] != tx]
            affected.add(r)
        for r2 in held.pop(tx, ()):
            del holders[r2][tx]
            affected.add(r2)
        finished.add(tx)
        for r2 in sorted(affected):
            process_queue(i, r2)

    def out_edges(w, posc):
        # Reachability-equivalent edge set: a queued request points at its predecessor in the
        # queue; the front request points at the incompatible holders.
        res = waiting[w]
        q = queues[res]
        if res not in posc:
            posc[res] = {e[0]: k for k, e in enumerate(q)}
        pos = posc[res][w]
        if pos > 0:
            return [q[pos - 1][0]]
        mode = q[0][1]
        return [h for h, m in holders.get(res, {}).items() if h != w and (mode == "X" or m == "X")]

    def cycle_members(start):
        # nodes on a cycle through `start` (every cycle created by a new wait passes through it)
        if start not in waiting:
            return []
        posc = {}
        fwd = {start: out_edges(start, posc)}
        stack = [start]
        while stack:
            u = stack.pop()
            for v in fwd[u]:
                if v not in fwd:
                    fwd[v] = out_edges(v, posc) if v in waiting else []
                    stack.append(v)
        rev = {}
        for u, vs in fwd.items():
            for v in vs:
                rev.setdefault(v, []).append(u)
        if start not in rev:
            return []
        back = {start}
        stack = [start]
        while stack:
            u = stack.pop()
            for v in rev.get(u, ()):
                if v not in back:
                    back.add(v)
                    stack.append(v)
        return list(back)

    for i, op in enumerate(ops):
        tx = op[1]
        if tx in waiting or tx in finished:
            log.append(("IGNORED", i, tx))
            continue
        if op[0] == "COMMIT":
            log.append(("COMMIT", i, tx))
            release(i, tx)
            continue
        mode, res = op[0], op[2]
        mine = holders.get(res, {}).get(tx)
        if mine == "X" or (mine == "S" and mode == "S"):
            log.append(("HELD", i, tx, res))
            continue
        if mine == "S":
            if len(holders[res]) == 1:
                holders[res][tx] = "X"
                log.append(("GRANT", i, tx, res, "X"))
                continue
            q = queues.setdefault(res, [])
            k = 0
            while k < len(q) and q[k][2]:
                k += 1
            q.insert(k, [tx, "X", True])
        else:
            q = queues.setdefault(res, [])
            if not q and compatible(mode, res, tx):
                holders.setdefault(res, {})[tx] = mode
                held.setdefault(tx, set()).add(res)
                log.append(("GRANT", i, tx, res, mode))
                continue
            q.append([tx, mode, False])
        waiting[tx] = res
        log.append(("WAIT", i, tx, res, "X" if mine == "S" else mode))
        while True:
            members = cycle_members(tx)
            if not members:
                break
            victim = max(members)
            log.append(("ABORT", i, victim))
            release(i, victim)
    return log
