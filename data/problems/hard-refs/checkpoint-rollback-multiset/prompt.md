Write a Python function:

    def run_ops(ops: list[tuple]) -> list

It simulates a multiset of ints (duplicates allowed) with checkpoints and rollback.
The multiset starts empty and no checkpoints exist. `ops` is processed in order and
EVERY operation appends exactly one value to the returned list:

- ("add", x): add one copy of x. Output: the multiset's size (with multiplicity) after
  the add.
- ("remove", x): if x is present, remove ONE copy and output True; otherwise output
  False and change nothing.
- ("checkpoint",): record the current contents as a new checkpoint. Checkpoint ids are
  1, 2, 3, ... in creation order and are never reused (even after invalidation). Output:
  the new checkpoint's id.
- ("rollback", c): checkpoint c is VALID if it has been created and has not been
  invalidated. If c is not valid (including any c that was never created, such as 0 or
  a negative number), output the string "BADCP" and change nothing. Otherwise restore the
  multiset to exactly the contents recorded at checkpoint c, permanently invalidate every
  checkpoint whose id is greater than c (checkpoint c itself stays valid and can be
  rolled back to again), and output the size after the restore.
- ("median",): output the LOWER median: for size s >= 1, the element at 1-based
  position (s + 1) // 2 of the contents sorted ascending (counting duplicates). Output
  None if the multiset is empty.
- ("count_less", x): output the number of elements (with multiplicity) strictly less
  than x.
- ("distinct",): output the number of distinct values present.

Input domain: at most 300,000 operations; every x is an int in [-10**9, 10**9]; c is an
int; operation names always have the arity shown.

Performance requirement: the function is called with 300,000 operations in which the
multiset holds up to ~100,000 elements while tens of thousands of checkpoints are taken
and rolled back to, interleaved with median / count_less queries, and must finish in a
few seconds. Copying the contents at each checkpoint, or sorting/scanning the contents
for each query, is far too slow.

Examples:
- run_ops([("add", 5), ("add", 1), ("checkpoint",), ("add", 9), ("add", 9), ("median",),
           ("rollback", 1), ("median",), ("distinct",), ("count_less", 5)])
  == [1, 2, 1, 3, 4, 5, 2, 1, 2, 1]
- run_ops([("checkpoint",), ("add", 3), ("checkpoint",), ("remove", 3), ("checkpoint",),
           ("rollback", 2), ("rollback", 3), ("checkpoint",), ("rollback", 1), ("rollback", 4),
           ("rollback", 1), ("remove", 3), ("median",)])
  == [1, 1, 2, True, 3, 1, "BADCP", 4, 0, "BADCP", 0, False, None]
  # rolling back to 2 invalidates 3; the next checkpoint gets id 4; rolling back to 1
  # invalidates 2 and 4, but 1 can be rolled back to again
