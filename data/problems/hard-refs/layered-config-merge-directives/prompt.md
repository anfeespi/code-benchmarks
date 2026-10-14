Write a Python function:

    def merge_layers(layers) -> tuple[dict, list[str]]

It merges a stack of JSON-like configuration layers (dicts whose values are dicts, lists,
strs, ints, floats, bools or None, nested arbitrarily) from left to right into one dict, and
returns `(merged, warnings)`. Layer keys may carry DIRECTIVES.

TOP LEVEL
- If `layers` is not a list: raise TypeError("layers must be a list").
- The result starts as an empty dict. Layers are merged one at a time in list order (layer
  index `L` is 0-based). Immediately before layer L is merged, if it is not a dict raise
  TypeError(f"layer {L} is not a dict") (so an error inside layer 0 is raised before layer 1
  is even looked at).

MERGING an overlay dict O into a target dict T at path P (the top-level call merges the
layer into the result at path "$"). The keys of O are processed one at a time in O's
iteration order. For each key K with value V:
1. If K is not a str: raise TypeError(f"layer {L}: non-string key at {P}").
2. Classify K and compute NAME:
   - K starts with "-": a DELETE directive, NAME = K[1:] (even if K also ends with "+").
   - otherwise, K ends with "+": an APPEND directive, NAME = K[:-1].
   - otherwise: a plain SET, NAME = K.
3. If NAME is the empty string: raise ValueError(f"layer {L}: empty key name at {P}").
4. Let Q be the path of NAME inside P (see PATHS). Then:
   - DELETE: if V is not None raise ValueError(f"layer {L}: delete directive needs null at {Q}").
     If NAME is a key of T, remove it from T; otherwise append the warning
     f"layer {L}: delete of missing key at {Q}".
   - APPEND: if V is not a list raise ValueError(f"layer {L}: append directive needs a list at {Q}").
     If NAME is not in T, set T[NAME] to (a copy of) V. If T[NAME] is a list, extend it with
     (copies of) V's elements. Otherwise raise
     ValueError(f"layer {L}: cannot append to {TYPE(T[NAME])} at {Q}").
   - SET: if NAME is already in T and TYPE(T[NAME]) != TYPE(V), first append the warning
     f"layer {L}: type change at {Q}: {TYPE(T[NAME])} -> {TYPE(V)}".
     Then, if V is a dict: if T[NAME] exists and is a dict, recursively merge V into T[NAME]
     at path Q; otherwise set T[NAME] to a new empty dict and recursively merge V into it at
     path Q (so directives inside V are processed even when nothing was there before).
     If V is not a dict, T[NAME] becomes (a copy of) V, replacing any old value.
   Values inside lists are opaque: dicts nested inside lists are copied as-is and never
   processed for directives.
TYPE(v) is one of "dict", "list", "str", "int", "float", "bool", "null" (bool is its own
type, never "int"; None is "null").

KEY ORDER of every dict in the result: a key keeps its existing position when its value is
replaced, merged or appended to; a newly created key goes at the end; a deleted key is
removed (if it is created again later it goes at the end).

PATHS: the root is "$". The path of NAME inside path P is P + "." + NAME when NAME fully
matches the regex [A-Za-z_][A-Za-z0-9_]* (ASCII only), otherwise
P + "[" + json.dumps(NAME, ensure_ascii=False) + "]". Directive paths use NAME (without the
"-" / "+" marker). Example: NAME "db" under "$" -> "$.db"; NAME "max-conn" under "$.db" ->
'$.db["max-conn"]'; NAME "2x" under "$" -> '$["2x"]'.

The first error raised aborts the whole call (no partial result is returned). `warnings` lists
every warning in the order produced. Inputs must not be mutated, and the returned structure
must share no dict or list objects with the inputs.

Examples:
    merge_layers([{"db": {"host": "a", "ports": [1]}, "debug": False},
                  {"db": {"ports+": [2, 3], "-user": None, "host": 7}, "debug": {"level": 1}}])
    == ({"db": {"host": 7, "ports": [1, 2, 3]}, "debug": {"level": 1}},
        ["layer 1: delete of missing key at $.db.user",
         "layer 1: type change at $.db.host: str -> int",
         "layer 1: type change at $.debug: bool -> dict"])

    merge_layers([{"a": 1}, {"a+": [2]}])
        raises ValueError("layer 1: cannot append to int at $.a")

    merge_layers([{"x": {"-": None}}])
        raises ValueError("layer 0: empty key name at $.x")
