N = 600


def gen(rng):
    nslots = rng.randint(1, 3)
    slots = ["s%d" % i for i in range(nslots)]
    prices = {s: 5 * rng.randint(1, 30) for s in slots}
    stock = {s: rng.randint(0, 3) for s in slots}
    bank = {}
    for d in (5, 10, 25, 100):
        if rng.random() < 0.7:
            bank[d] = rng.randint(0, 3)
    timeout = rng.randint(1, 8)
    n = rng.randint(0, 30)
    t = 0
    events = []
    for _ in range(n):
        t += rng.choice([0, 0, 1, 1, 2, 3, timeout, timeout - 1, timeout + 1])
        r = rng.random()
        if r < 0.6:
            events.append((t, "coin", rng.choice([5, 10, 25, 100, 25, 10, 5, 1, 50])))
        elif r < 0.9:
            events.append((t, "select", rng.choice(slots + ["zz"])))
        else:
            events.append((t, "cancel", None))
    if n >= 2 and rng.random() < 0.05:
        events[0] = (events[-1][0] + 1,) + events[0][1:]
    return (prices, stock, bank, events, timeout)
