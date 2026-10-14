Write a Python function:

    def run_ops(ops: list[tuple]) -> list

It simulates a versioned key-value store whose history can branch. Keys and values are
ints. Versions are immutable snapshots identified by non-negative int ids. Version 0
always exists and is the empty map. New versions are numbered 1, 2, 3, ... in the order
in which they are created; ids are never reused. Every update operation derives a new
version from ANY existing version (not necessarily the latest), so history forms a tree.

`ops` is processed in order and EVERY operation appends exactly one value to the
returned list. In every operation the second element `v` is an int; if no version with
id `v` exists at that moment (v < 0 or v greater than the largest id created so far),
the output is the string "BADVER" and nothing else happens. Otherwise:

- ("set", v, key, value): create a new version equal to version v except that `key`
  maps to `value` (inserted or overwritten; a new version is created even if the value
  is unchanged). Output: the new version's id.
- ("del", v, key): if `key` is not present in version v, output the string "NOKEY" and
  create NO version. Otherwise create a new version equal to version v without `key`
  and output its id.
- ("get", v, key): output the value of `key` in version v, or None if absent.
- ("count", v, lo, hi): output the number of keys k in version v with lo <= k <= hi
  (0 when lo > hi).
- ("sum", v, lo, hi): output the sum of the values of the keys k in version v with
  lo <= k <= hi (0 when there are none or lo > hi).
- ("kth", v, k): output the k-th smallest key (1-based) of version v, or None if k < 1
  or k exceeds the number of keys in version v.

Existing versions are never modified by later operations.

Input domain: at most 150,000 operations; keys, values, lo, hi in [-10**9, 10**9];
k in [-10**9, 10**9]; operation names are always one of the six above with the arity
shown.

Performance requirement: the function is called with 150,000 operations that build
versions holding tens of thousands of keys each, branching from random older versions,
and must finish in a few seconds. Copying a version's contents (or rescanning all of its
keys) for each operation is far too slow.

Examples:
- run_ops([("set", 0, 5, 50), ("set", 1, 2, 20), ("set", 1, 9, 90), ("kth", 2, 1),
           ("kth", 3, 1), ("sum", 3, 0, 10), ("get", 2, 9), ("get", 0, 5)])
  == [1, 2, 3, 2, 5, 140, None, None]
  # versions 2 and 3 both branch from version 1 and do not see each other's keys
- run_ops([("del", 0, 7), ("set", 0, 7, 1), ("del", 1, 7), ("del", 2, 7), ("count", 2, -10, 10),
           ("count", 1, 7, 7), ("get", 3, 7), ("kth", 9, 1)])
  == ["NOKEY", 1, 2, "NOKEY", 0, 1, "BADVER", "BADVER"]
  # failed deletes create no version, so after these ops only versions 0, 1, 2 exist
