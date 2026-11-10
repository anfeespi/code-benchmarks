# Independent reference: advances time one unit at a time and keeps the escrow as a list.
def simulate_vending(prices, stock, bank, events, timeout):
    for a, b in zip(events, events[1:]):
        if b[0] < a[0]:
            raise ValueError("events out of order")
    st = {k: v for k, v in stock.items()}
    coins = {5: 0, 10: 0, 25: 0, 100: 0}
    for k, v in bank.items():
        coins[k] = v
    esc = []
    log = []
    deadline = None  # time at which the escrow is auto-returned
    end = (events[-1][0] if events else 0) + timeout + 1
    idx = 0
    T = 0
    while T <= end:
        if esc and deadline == T:
            log.append(("TIMEOUT", T, tuple(sorted(esc)[::-1])))
            esc = []
        while idx < len(events) and events[idx][0] == T:
            _, kind, arg = events[idx]
            idx += 1
            if kind == "coin":
                if arg in (5, 10, 25, 100) and len(esc) < 10:
                    esc.append(arg)
                    deadline = T + timeout
                else:
                    log.append(("REJECT", T, arg))
            elif kind == "cancel":
                deadline = T + timeout
                if esc:
                    log.append(("RETURN", T, tuple(sorted(esc)[::-1])))
                    esc = []
            else:
                deadline = T + timeout
                if arg not in prices:
                    log.append(("UNKNOWN", T, arg))
                elif st[arg] <= 0:
                    log.append(("SOLD_OUT", T, arg))
                elif sum(esc) < prices[arg]:
                    log.append(("NEED", T, prices[arg] - sum(esc)))
                else:
                    pool = dict(coins)
                    for c in esc:
                        pool[c] += 1
                    owe = sum(esc) - prices[arg]
                    given = []
                    while owe > 0:
                        usable = [d for d in (5, 10, 25, 100) if pool[d] > 0 and d <= owe]
                        if not usable:
                            break
                        d = max(usable)
                        pool[d] -= 1
                        owe -= d
                        given.append(d)
                    if owe == 0:
                        coins = pool
                        st[arg] -= 1
                        esc = []
                        log.append(("VEND", T, arg, tuple(given)))
                    else:
                        log.append(("EXACT_ONLY", T, arg))
        T += 1
    return log, (coins[5], coins[10], coins[25], coins[100])
