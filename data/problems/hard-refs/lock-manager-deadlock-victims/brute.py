# Independent reference: rebuilds the full wait-for graph after every step and tests every
# node for self-reachability.
def run_lock_manager(ops):
    locks = []      # list of (tx, res, mode) currently held
    queue = []      # global list of pending requests in queue order per resource: (res, tx, mode, upgrade)
    done = set()
    log = []

    def holders_of(res):
        return {t: m for (t, r, m) in locks if r == res}

    def queued(res):
        return [e for e in queue if e[0] == res]

    def is_waiting(tx):
        return any(e[1] == tx for e in queue)

    def ok_with(res, tx, mode):
        return all(not (h != tx and (mode == "X" or m == "X")) for h, m in holders_of(res).items())

    def grant(res, tx, mode):
        for k, (t, r, m) in enumerate(locks):
            if t == tx and r == res:
                locks[k] = (t, r, mode)
                return
        locks.append((tx, res, mode))

    def drain(i, res):
        while True:
            q = queued(res)
            if not q:
                return
            _, tx, mode, _ = q[0]
            if not ok_with(res, tx, mode):
                return
            queue.remove(q[0])
            grant(res, tx, mode)
            log.append(("GRANT", i, tx, res, mode))

    def drop(i, tx):
        touched = set()
        for e in list(queue):
            if e[1] == tx:
                queue.remove(e)
                touched.add(e[0])
        for (t, r, m) in list(locks):
            if t == tx:
                locks.remove((t, r, m))
                touched.add(r)
        done.add(tx)
        for r in sorted(touched):
            drain(i, r)

    def graph():
        g = {}
        for e in queue:
            res, w, mode, up = e
            q = queued(res)
            idx = q.index(e)
            tgt = set(x[1] for x in q[:idx])
            for h, m in holders_of(res).items():
                if h != w and (mode == "X" or m == "X"):
                    tgt.add(h)
            g[w] = tgt
        return g

    def on_cycle(g):
        res = []
        for s in g:
            seen = set()
            stack = list(g[s])
            while stack:
                u = stack.pop()
                if u == s:
                    res.append(s)
                    break
                if u in seen:
                    continue
                seen.add(u)
                stack.extend(g.get(u, ()))
        return res

    for i, op in enumerate(ops):
        tx = op[1]
        if tx in done or is_waiting(tx):
            log.append(("IGNORED", i, tx))
        elif op[0] == "COMMIT":
            log.append(("COMMIT", i, tx))
            drop(i, tx)
        else:
            mode, res = op[0], op[2]
            cur = holders_of(res).get(tx)
            if cur == "X" or (cur == "S" and mode == "S"):
                log.append(("HELD", i, tx, res))
            elif cur == "S":
                if set(holders_of(res)) == {tx}:
                    grant(res, tx, "X")
                    log.append(("GRANT", i, tx, res, "X"))
                else:
                    q = queued(res)
                    ups = [e for e in q if e[3]]
                    if ups:
                        pos = queue.index(ups[-1]) + 1
                    elif q:
                        pos = queue.index(q[0])
                    else:
                        pos = len(queue)
                    queue.insert(pos, (res, tx, "X", True))
                    log.append(("WAIT", i, tx, res, "X"))
            else:
                if not queued(res) and ok_with(res, tx, mode):
                    grant(res, tx, mode)
                    log.append(("GRANT", i, tx, res, mode))
                else:
                    queue.append((res, tx, mode, False))
                    log.append(("WAIT", i, tx, res, mode))
        while True:
            c = on_cycle(graph())
            if not c:
                break
            v = max(c)
            log.append(("ABORT", i, v))
            drop(i, v)
    return log
