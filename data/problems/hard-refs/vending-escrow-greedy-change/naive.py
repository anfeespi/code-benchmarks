# Correct but walks every time unit: hopeless when timestamps reach 10**12.
def simulate_vending(prices, stock, bank, events, timeout):
    for a, b in zip(events, events[1:]):
        if b[0] < a[0]:
            raise ValueError("events out of order")
    st = dict(stock)
    coins = {5: 0, 10: 0, 25: 0, 100: 0}
    coins.update(bank)
    esc, log, deadline, idx, T = [], [], None, 0, 0
    end = (events[-1][0] if events else 0) + timeout + 1
    while T <= end:
        if esc and deadline == T:
            log.append(("TIMEOUT", T, tuple(sorted(esc, reverse=True))))
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
                continue
            deadline = T + timeout
            if kind == "cancel":
                if esc:
                    log.append(("RETURN", T, tuple(sorted(esc, reverse=True))))
                    esc = []
            elif arg not in prices:
                log.append(("UNKNOWN", T, arg))
            elif st[arg] <= 0:
                log.append(("SOLD_OUT", T, arg))
            elif sum(esc) < prices[arg]:
                log.append(("NEED", T, prices[arg] - sum(esc)))
            else:
                pool = dict(coins)
                for c in esc:
                    pool[c] += 1
                owe, given = sum(esc) - prices[arg], []
                for d in (100, 25, 10, 5):
                    k = min(pool[d], owe // d)
                    pool[d] -= k
                    owe -= k * d
                    given += [d] * k
                if owe == 0:
                    coins, esc = pool, []
                    st[arg] -= 1
                    log.append(("VEND", T, arg, tuple(given)))
                else:
                    log.append(("EXACT_ONLY", T, arg))
        T += 1
    return log, (coins[5], coins[10], coins[25], coins[100])
