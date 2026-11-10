# Independent reference: walks every time unit, applying refills token by token.
def admit_requests(requests, config):
    for i in range(1, len(requests)):
        if requests[i][0] < requests[i - 1][0]:
            raise ValueError("requests out of order")
    C = config
    bucket = {}
    strikes = {}
    banned_from = {}
    g = C["gcap"]
    status = [None] * len(requests)
    i = 0
    T = 0
    last = requests[-1][0] if requests else -1
    while T <= last:
        if T > 0:
            if T % C["period"] == 0:
                for k in bucket:
                    if bucket[k] < C["cap"]:
                        bucket[k] += 1
            if T % C["gperiod"] == 0 and g < C["gcap"]:
                g += 1
        while i < len(requests) and requests[i][0] == T:
            _, c, cost, vip = requests[i]
            if c not in bucket:
                bucket[c] = C["cap"]
                strikes[c] = []
            s = None
            b = banned_from.get(c)
            if b is not None and b <= T < b + C["ban"]:
                s = "BANNED"
            elif bucket[c] < cost:
                strikes[c].append(T)
                recent = [x for x in strikes[c] if T - C["window"] < x <= T]
                if len(recent) >= C["strikes"]:
                    strikes[c] = []
                    banned_from[c] = T
                    s = "BAN"
                else:
                    s = "DENY"
            else:
                left = g - cost
                ok = left >= 0 if vip else left >= C["reserve"]
                if ok:
                    g = left
                    bucket[c] -= cost
                    s = "OK"
                else:
                    s = "BUSY"
            status[i] = s
            i += 1
        T += 1
    return status
