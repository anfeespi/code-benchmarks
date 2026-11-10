Write a Python function:

    def admit_requests(requests, config)

It simulates an API gateway rate limiter and returns a list of status strings, one per
request, in input order.

`config` is a dict with these int keys (all present):
- "cap"      client bucket capacity (>= 1)
- "period"   client refill period (>= 1)
- "gcap"     global bucket capacity (>= 1)
- "gperiod"  global refill period (>= 1)
- "reserve"  global reserve for VIP traffic (0 <= reserve <= gcap)
- "strikes"  strikes that trigger a ban (>= 1)
- "window"   strike window length (>= 1)
- "ban"      ban length (>= 1)

`requests` is a list of tuples `(t, client, cost, vip)`: `t` an int >= 0, `client` a
non-empty str, `cost` an int >= 1, `vip` a bool. Requests with the same `t` are
processed in list order. If some request's `t` is smaller than the previous request's `t`,
raise ValueError before producing anything.

Buckets
- Each client has its own bucket holding an integer number of tokens. The bucket is
  created FULL (cap tokens) at the moment of the client's first request.
- The global bucket is created full (gcap tokens) at time 0.
- Refills happen at absolute times: at every time t that is a positive multiple of
  `period`, every existing client bucket gains 1 token; at every time t that is a positive
  multiple of `gperiod`, the global bucket gains 1 token. A bucket never exceeds its
  capacity (a refill into a full bucket is lost). Refills scheduled at time t happen
  before any request at time t is processed. Refills keep happening while a client is
  banned.

Processing one request (t, c, cost, vip), first matching rule wins:
1. If c is banned at time t (see below): status "BANNED". Nothing else changes (no
   tokens, no strike).
2. If c's bucket holds fewer than `cost` tokens: the request is denied and c receives a
   STRIKE at time t. If c now has at least `strikes` strikes with times in the half-open
   interval (t - window, t] (this strike included), c becomes banned: status "BAN", c's
   strike history is erased, and c is banned at every time t' with t <= t' < t + ban
   (so later requests of c at the same time t are "BANNED"). Otherwise status "DENY".
3. Otherwise check the global bucket. A non-VIP request needs
   global_tokens - cost >= reserve; a VIP request needs global_tokens >= cost. If the
   check fails: status "BUSY" (no tokens taken, NO strike).
4. Otherwise: take `cost` tokens from c's bucket and from the global bucket; status "OK".

Strike times older than the window simply stop counting; a ban erases all of c's earlier
strikes. A client's bucket is not touched by rules 1-3.

Input domain: up to 200,000 requests, up to 5,000 distinct clients, times up to 10**12,
all config values up to 10**12.

Examples (cfg = {"cap": 2, "period": 10, "gcap": 3, "gperiod": 5, "reserve": 1,
"strikes": 2, "window": 7, "ban": 4}):
- admit_requests([(0, "a", 1, False), (0, "a", 1, False), (0, "b", 1, False),
                  (0, "b", 1, True), (1, "b", 1, True)], cfg)
  == ["OK", "OK", "BUSY", "OK", "BUSY"]
  # global: 3 -> 2 -> 1; b's non-VIP request would leave 0 < reserve; the VIP one may use
  # the reserve; at t=1 the global bucket is empty (next global refill at t=5)
- admit_requests([(0, "a", 3, False), (6, "a", 3, False), (6, "a", 1, False),
                  (9, "a", 1, False), (10, "a", 1, False), (13, "a", 3, False)], cfg)
  == ["DENY", "BAN", "BANNED", "BANNED", "OK", "DENY"]
  # cost 3 > cap 2 always strikes; strikes at 0 and 6 are within (6-7, 6] -> ban for
  # 6 <= t' < 10; at t=13 the only strike in (6, 13] is the new one, so no ban
- admit_requests([(7, "a", 1, False), (9, "a", 1, False), (10, "a", 1, False),
                  (10, "a", 1, False), (30, "a", 1, False)],
                 {"cap": 1, "period": 10, "gcap": 5, "gperiod": 1, "reserve": 0,
                  "strikes": 3, "window": 100, "ban": 50})
  == ["OK", "DENY", "OK", "DENY", "OK"]
  # a's bucket (created at t=7) gets its token back at the absolute time 10, not at 17
