Write a Python function:

    def simulate_vending(prices, stock, bank, events, timeout)

It simulates a coin-operated vending machine and returns `(log, final_bank)`.

Inputs
- `prices`: dict mapping slot name (str) to price (int > 0, a multiple of 5).
- `stock`: dict with exactly the same keys as `prices`, mapping slot to items left (int >= 0).
- `bank`: dict mapping a coin value to how many such coins the machine holds for giving
  change. Keys are a subset of {5, 10, 25, 100}; a missing key means 0 coins.
- `events`: list of tuples `(t, kind, arg)`, `t` an int >= 0. Kinds:
    ("coin", value)   - a customer inserts a coin of int `value`
    ("select", slot)  - a customer presses the button of str `slot`
    ("cancel", None)  - a customer presses the coin-return lever
  If any event's `t` is smaller than the previous event's `t`, raise ValueError (before
  producing anything). Events with equal `t` are processed in list order.
- `timeout`: int >= 1.
Do not mutate the inputs.

Machine state: the BANK (coins available for change, initialised from `bank`), the STOCK,
and the ESCROW: the coins inserted by the current customer that have not been spent or
returned yet (an ordered collection, initially empty). The machine accepts only the coin
values 5, 10, 25 and 100.

Event rules
1. ("coin", v): if v is not an accepted value, OR the escrow already holds 10 coins, the
   coin is rejected: log ("REJECT", t, v); nothing else changes. Otherwise v is added to
   the escrow (no log entry).
2. ("select", s), checked in this order:
   a. s is not a key of `prices` -> log ("UNKNOWN", t, s).
   b. stock of s is 0 -> log ("SOLD_OUT", t, s).
   c. escrow total < price of s -> log ("NEED", t, price - escrow_total).
   d. Otherwise attempt the sale: first move ALL escrow coins into the bank, then compute
      change = escrow_total - price GREEDILY: for coin value d in 100, 25, 10, 5 (in that
      order) take k = min(bank count of d, remaining // d) coins of value d out of the
      bank. If the remaining amount is then 0, the sale succeeds: stock of s decreases by
      1, the escrow is now empty, and log ("VEND", t, s, change_coins) where change_coins
      is a tuple of the coin values handed out in non-increasing order (empty tuple when
      the change is 0). If the remaining amount is not 0 the sale is cancelled and fully
      rolled back (bank and escrow exactly as before step d) and log ("EXACT_ONLY", t, s).
      Note: the greedy rule is mandatory even when some other combination of bank coins
      could have made the change.
3. ("cancel", None): if the escrow is non-empty, log ("RETURN", t, coins) and empty the
   escrow; coins is a tuple of the escrow coins in non-increasing order. If the escrow is
   empty nothing is logged.

Activity and automatic return
- An ACTIVITY is any "select" event (whatever its outcome), any "cancel" event, and any
  "coin" event whose coin was NOT rejected. A rejected coin is not an activity.
- Let `last` be the time of the most recent activity. Whenever the escrow is non-empty,
  the machine automatically returns it at time `last + timeout`: log
  ("TIMEOUT", last + timeout, coins) (coins in non-increasing order) and empty the escrow.
- The automatic return happens BEFORE processing any event whose `t >= last + timeout`
  (so an event at exactly `last + timeout` sees an empty escrow). After the last event,
  a still-pending automatic return is also performed and logged.

Return value
- `log`: list of the tuples described above, in the order they happen.
- `final_bank`: tuple (count of 5s, count of 10s, count of 25s, count of 100s) in the
  bank after everything (including the final automatic return, which never touches the
  bank).

Input domain: up to 200,000 events, times up to 10**12, timeout up to 10**12.

Examples:
- simulate_vending({"A": 65}, {"A": 2}, {5: 1, 10: 0, 25: 3},
                   [(0, "coin", 100), (1, "select", "A")], 30)
  == ([("EXACT_ONLY", 1, "A"), ("TIMEOUT", 31, (100,))], (1, 0, 3, 0))
  # change 35: greedy takes one 25, then no 10, and one 5 leaves 5 unpaid -> rolled back;
  # the select at t=1 is the last activity, so the 100 comes back at 1 + 30
- simulate_vending({"A": 20}, {"A": 1}, {},
                   [(0, "coin", 25), (2, "coin", 3), (5, "coin", 5), (6, "select", "A")], 4)
  == ([("REJECT", 2, 3), ("TIMEOUT", 4, (25,)), ("NEED", 6, 15), ("TIMEOUT", 10, (5,))],
      (0, 0, 0, 0))
  # the rejected coin is not an activity, so the 25 inserted at t=0 is returned at t=4
- simulate_vending({"B": 30}, {"B": 3}, {5: 2, 10: 3, 25: 1},
                   [(0, "coin", 100), (3, "select", "B"), (4, "coin", 25), (4, "coin", 10),
                    (5, "select", "B")], 5)
  == ([("EXACT_ONLY", 3, "B"), ("VEND", 5, "B", (100, 5))], (1, 4, 2, 0))
  # at t=5 the escrow (100, 25, 10) enters the bank first, so the change of 105 can use
  # the customer's own 100
