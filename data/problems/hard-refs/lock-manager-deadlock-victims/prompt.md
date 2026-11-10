Write a Python function:

    def run_lock_manager(ops)

It simulates a lock manager with shared/exclusive locks, FIFO wait queues, lock upgrades
and deadlock resolution, and returns the list of log records it produces.

Transactions are identified by ints; a SMALLER id means an OLDER transaction. Resources
are identified by strs. `ops` is a list of operations; operation `i` is its 0-based
position in the list:
    ("S", tx, res)     tx requests a shared lock on res
    ("X", tx, res)     tx requests an exclusive lock on res
    ("COMMIT", tx)     tx commits

Transaction states: a transaction becomes ACTIVE at its first operation. It is WAITING
while it has a queued lock request, and it is FINISHED after it commits or is aborted.
Lock compatibility: S is compatible only with S; X is compatible with nothing. A
transaction holds at most one lock (S or X) per resource.

Processing operation i of transaction T:
1. If T is WAITING or FINISHED: log ("IGNORED", i, T); nothing else happens.
2. ("COMMIT", T): log ("COMMIT", i, T), then T RELEASES (see below); T is FINISHED.
3. Lock request with mode M on resource R:
   a. If T already holds X on R, or holds S on R and M is S: log ("HELD", i, T, R).
   b. If T holds S on R and M is X (an UPGRADE): if T is the only holder of R, T's lock
      becomes X immediately and log ("GRANT", i, T, R, "X") (even if other requests are
      queued on R). Otherwise the request is queued on R directly BEHIND any upgrade
      requests already queued on R but AHEAD of all other queued requests; log
      ("WAIT", i, T, R, "X").
   c. Otherwise (T holds nothing on R): if R's queue is empty and M is compatible with
      every current holder of R, grant it: log ("GRANT", i, T, R, M). Otherwise append
      the request to the BACK of R's queue: log ("WAIT", i, T, R, M).

RELEASE of transaction T (on commit or abort):
- First remove T's queued request (if any) from its queue; then drop every lock T holds.
- Then, for every AFFECTED resource (each resource where T held a lock, plus the resource
  of T's removed queued request) in ascending order of resource name (plain Python str
  comparison), PROCESS THE QUEUE:
  repeatedly look at the request at the front of the queue; if it is grantable, remove it
  from the queue, grant it and log ("GRANT", i, U, R, mode) where U is the requester and
  i is the index of the operation being processed; otherwise stop. A front request of
  transaction U with mode M is grantable when M is compatible with every holder of R
  other than U (for an upgrade, U itself holds S and is not counted). A granted
  transaction stops WAITING.

Deadlocks. The wait-for graph has an edge W -> V when W is WAITING with request mode M on
resource R and either (1) V != W holds a lock on R that is incompatible with M (for an
upgrade request, every other holder of R), or (2) V's request is queued on R ahead of W's
request. After an operation's steps above (and after each abort below), while the
wait-for graph contains a cycle: let VICTIM be the transaction with the LARGEST id among
all transactions that lie on at least one cycle; log ("ABORT", i, VICTIM), then the victim
RELEASES (queue processing logs its GRANTs with the same i) and becomes FINISHED.

Return the list of all log tuples in the order produced. `ops` is not modified.

Input domain: up to 30,000 operations, up to 5,000 transactions, up to 2,000 resources.

Performance requirement: the function is called with 30,000 operations in which hundreds
of transactions are waiting at the same time and queues grow to hundreds of requests; it
must finish within a few seconds. Rebuilding and searching the whole wait-for graph after
every operation is too slow.

Examples:
- run_lock_manager([("S", 1, "a"), ("S", 2, "a"), ("X", 3, "a"), ("S", 4, "a"),
                    ("COMMIT", 1), ("COMMIT", 2)])
  == [("GRANT", 0, 1, "a", "S"), ("GRANT", 1, 2, "a", "S"), ("WAIT", 2, 3, "a", "X"),
      ("WAIT", 3, 4, "a", "S"), ("COMMIT", 4, 1), ("COMMIT", 5, 2),
      ("GRANT", 5, 3, "a", "X")]
  # 4 waits behind the queued X even though S is compatible with the S holders
- run_lock_manager([("S", 1, "r"), ("S", 2, "r"), ("X", 1, "r"), ("X", 2, "r"),
                    ("S", 2, "q")])
  == [("GRANT", 0, 1, "r", "S"), ("GRANT", 1, 2, "r", "S"), ("WAIT", 2, 1, "r", "X"),
      ("WAIT", 3, 2, "r", "X"), ("ABORT", 3, 2), ("GRANT", 3, 1, "r", "X"),
      ("IGNORED", 4, 2)]
  # two upgrades on r deadlock; 2 is the youngest on the cycle
- run_lock_manager([("X", 1, "a"), ("X", 2, "b"), ("X", 1, "b"), ("S", 3, "b"),
                    ("X", 2, "a")])
  == [("GRANT", 0, 1, "a", "X"), ("GRANT", 1, 2, "b", "X"), ("WAIT", 2, 1, "b", "X"),
      ("WAIT", 3, 3, "b", "S"), ("WAIT", 4, 2, "a", "X"), ("ABORT", 4, 2),
      ("GRANT", 4, 1, "b", "X")]
  # cycle 1 -> 2 -> 1; transaction 3 is not on a cycle, it stays queued behind 1
