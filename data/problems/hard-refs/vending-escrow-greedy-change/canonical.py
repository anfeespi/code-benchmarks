DENOMS = (100, 25, 10, 5)


def simulate_vending(prices, stock, bank, events, timeout):
    prev = None
    for ev in events:
        if prev is not None and ev[0] < prev:
            raise ValueError("events out of order")
        prev = ev[0]
    stock = dict(stock)
    bk = {d: bank.get(d, 0) for d in DENOMS}
    escrow = []
    log = []
    last = None

    def flush_if_due(t):
        if escrow and (t is None or t >= last + timeout):
            log.append(("TIMEOUT", last + timeout, tuple(sorted(escrow, reverse=True))))
            escrow.clear()

    for t, kind, arg in events:
        flush_if_due(t)
        if kind == "coin":
            if arg not in DENOMS or len(escrow) >= 10:
                log.append(("REJECT", t, arg))
                continue
            escrow.append(arg)
            last = t
        elif kind == "select":
            last = t
            if arg not in prices:
                log.append(("UNKNOWN", t, arg))
                continue
            if stock[arg] == 0:
                log.append(("SOLD_OUT", t, arg))
                continue
            total = sum(escrow)
            price = prices[arg]
            if total < price:
                log.append(("NEED", t, price - total))
                continue
            trial = dict(bk)
            for c in escrow:
                trial[c] += 1
            rem = total - price
            change = []
            for d in DENOMS:
                k = min(trial[d], rem // d)
                if k:
                    trial[d] -= k
                    rem -= k * d
                    change.extend([d] * k)
            if rem:
                log.append(("EXACT_ONLY", t, arg))
                continue
            bk = trial
            stock[arg] -= 1
            escrow.clear()
            log.append(("VEND", t, arg, tuple(change)))
        elif kind == "cancel":
            last = t
            if escrow:
                log.append(("RETURN", t, tuple(sorted(escrow, reverse=True))))
                escrow.clear()
    flush_if_due(None)
    return log, (bk[5], bk[10], bk[25], bk[100])
