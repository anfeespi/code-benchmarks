from collections import deque


def admit_requests(requests, config):
    for a, b in zip(requests, requests[1:]):
        if b[0] < a[0]:
            raise ValueError("requests out of order")
    cap, period = config["cap"], config["period"]
    gcap, gperiod = config["gcap"], config["gperiod"]
    reserve, need, window, ban = config["reserve"], config["strikes"], config["window"], config["ban"]
    g_tokens, g_last = gcap, 0
    clients = {}  # name -> [tokens, last_update_time, strikes deque, banned_until]
    out = []
    for t, c, cost, vip in requests:
        g_tokens = min(gcap, g_tokens + (t // gperiod - g_last // gperiod))
        g_last = t
        st = clients.get(c)
        if st is None:
            st = clients[c] = [cap, t, deque(), None]
        else:
            st[0] = min(cap, st[0] + (t // period - st[1] // period))
            st[1] = t
        if st[3] is not None and t < st[3]:
            out.append("BANNED")
            continue
        if st[0] < cost:
            dq = st[2]
            dq.append(t)
            while dq and dq[0] <= t - window:
                dq.popleft()
            if len(dq) >= need:
                dq.clear()
                st[3] = t + ban
                out.append("BAN")
            else:
                out.append("DENY")
            continue
        if (g_tokens < cost) if vip else (g_tokens - cost < reserve):
            out.append("BUSY")
            continue
        st[0] -= cost
        g_tokens -= cost
        out.append("OK")
    return out
