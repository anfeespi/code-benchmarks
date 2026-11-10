Write a Python function:

    def run_kiosk(levels, threshold, patience, arrivals)

It simulates an automated battery-swap kiosk for delivery drones and returns the list of
outcomes.

Inputs
- `levels`: list of ints in [0, 100]; `levels[k]` is the charge of the battery sitting in
  slot k at time 0. There are len(levels) >= 1 slots, numbered from 0.
- `threshold`: int in [1, 100]; a battery may be handed out only if its charge is
  >= threshold.
- `patience`: int >= 0.
- `arrivals`: list of tuples `(t, drone, charge)`: `t` an int >= 0, `drone` a unique str,
  `charge` an int in [0, 100] (the charge of the battery the drone brings). Arrivals with
  the same `t` are handled in list order. If some arrival's `t` is smaller than the
  previous arrival's `t`, raise ValueError before doing anything.

Charging: every battery in a slot gains exactly 1 unit of charge per time unit, capped at
100. A battery placed into a slot at time t0 with charge c has charge
min(100, c + (t - t0)) at any time t >= t0. Charge is only ever an integer.

A SWAP of drone D at time t: among the slots whose battery has charge >= threshold at time
t, pick the one with the HIGHEST charge (ties: the lowest slot index). D takes that
battery and puts its own battery (with D's arrival charge) into the same slot at time t.
Record (drone, "SWAP", t, slot). The deposited battery can be handed out again at the same
time t if its charge is >= threshold.

Waiting drones form a FIFO queue. At each integer time t, the kiosk does, in this order:
1. Serve the queue: while the queue is non-empty and some slot has a battery with charge
   >= threshold, the drone at the front of the queue leaves the queue and SWAPs.
2. Handle the arrivals with this `t`, in list order: an arriving drone SWAPs immediately
   if the queue is empty and some slot has charge >= threshold; otherwise it joins the
   back of the queue.
3. Give up: every drone still in the queue whose arrival time + patience <= t leaves the
   queue, in queue order: record (drone, "LEFT", t).
(So a drone with patience 0 that cannot swap on arrival leaves at its arrival time, and a
drone whose patience runs out at time t can still be served in step 1 of time t.)

Return the list of records in the order they are produced. Every drone produces exactly
one record. `arrivals` is not modified.

Input domain: up to 100,000 arrivals, up to 20 slots, times and patience up to 10**12.
Stepping through time one unit at a time is far too slow; the function must finish within
a few seconds on the largest inputs.

Examples:
- run_kiosk([50, 80], 60, 15, [(0, "a", 10), (0, "b", 0), (3, "c", 70)])
  == [("a", "SWAP", 0, 1), ("b", "SWAP", 10, 0), ("c", "LEFT", 18)]
  # at t=0 only slot 1 (80) is >= 60, so b queues; slot 0 reaches 60 at t=10 and b takes
  # it; slot 1 (a's battery, 10 at t=0) reaches 60 only at t=50, after c gives up at 3+15
- run_kiosk([100], 90, 0, [(0, "x", 95), (0, "y", 20), (0, "z", 0)])
  == [("x", "SWAP", 0, 0), ("y", "SWAP", 0, 0), ("z", "LEFT", 0)]
  # y receives the 95 battery that x deposited a moment earlier
- run_kiosk([70, 70, 40], 60, 0, [(0, "p", 65), (0, "q", 0), (0, "r", 0), (0, "s", 0)])
  == [("p", "SWAP", 0, 0), ("q", "SWAP", 0, 1), ("r", "SWAP", 0, 0), ("s", "LEFT", 0)]
