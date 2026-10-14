# Correct but rebuilds the whole wait-for graph (all edges) and runs Tarjan after every wait.
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

    def cycle_members(start):
        g = {}
        for res, q in queues.items():
            for k, (w, mode, up) in enumerate(q):
                t = [e[0] for e in q[:k]]
                t += [h for h, m in holders.get(res, {}).items() if h != w and (mode == "X" or m == "X")]
                g[w] = t
        import sys
        sys.setrecursionlimit(100000)
        idx = {}; low = {}; st = []; on = set(); out = []; c = [0]
        def sc(v):
            idx[v] = low[v] = c[0]; c[0] += 1; st.append(v); on.add(v)
            for u in g.get(v, ()):
                if u not in idx:
                    sc(u); low[v] = min(low[v], low[u])
                elif u in on:
                    low[v] = min(low[v], idx[u])
            if low[v] == idx[v]:
                comp = []
                while True:
                    u = st.pop(); on.discard(u); comp.append(u)
                    if u == v: break
                if len(comp) > 1: out.extend(comp)
        for v in g:
            if v not in idx: sc(v)
        return out

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
