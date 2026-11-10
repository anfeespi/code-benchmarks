Write a Python function:

    def pick_version(available, constraint) -> str | None

It returns the highest version in `available` that satisfies `constraint` (a small
constraint language described below), or None if no version satisfies it.

VERSIONS
A version is a str of the form `X.Y.Z` or `X.Y.Z~rcN`, where X, Y, Z are decimal integers
written with ASCII digits and without leading zeros (so "0" is fine, "01" is not), and N is
such an integer with N >= 1. Nothing else is allowed (no spaces, no "v" prefix, no other
suffix). Versions are ordered by (X, Y, Z) numerically; for equal (X, Y, Z) every release
candidate is LOWER than the plain release, and release candidates are ordered by N.
So 1.2.3~rc1 < 1.2.3~rc2 < 1.2.3 < 1.2.4~rc1 < 1.10.0.

CONSTRAINT LANGUAGE
- The constraint is split on "|" into ALTERNATIVES (numbered from 1, left to right); a version
  satisfies the constraint if it satisfies at least one alternative.
- Each alternative has the spaces (" " only, no other whitespace) at both ends removed. If it
  then starts with "?", the alternative ALLOWS RELEASE CANDIDATES; the "?" is removed and the
  remainder again has surrounding spaces removed. The remainder is split on "," into CLAUSES
  (numbered from 1), each of which has surrounding spaces removed.
- A version satisfies an alternative if it satisfies EVERY clause of it AND (it is not a
  release candidate OR the alternative allows release candidates). Without "?", release
  candidates never match, even "=1.0.0~rc1".
- Valid clauses (V is a full version as defined above, possibly with ~rcN):
    *          matches every version
    =V  or V   equal to V
    !=V        not equal to V
    >V  >=V  <V  <=V   compared with V in the version order above
    X.*        major equals X              (X written like a version number part)
    X.Y.*      major equals X and minor equals Y
    @X.Y       major equals X and minor >= Y
  Anything else (including inner spaces, "==1.0.0", "<1.*", "@1", "1.2.3.*", "") is invalid.

VALIDATION ORDER (the first failure raises; validation is complete before any matching):
1. `available` is not a list -> TypeError("available must be a list")
2. each element in index order: not a str or not a valid version ->
   ValueError(f"invalid version at index {i}: {element!r}")
3. `constraint` is not a str -> TypeError("constraint must be a str")
4. `constraint` is empty or consists only of spaces -> ValueError("empty constraint")
5. alternatives left to right; within an alternative:
   - empty after removing spaces and the optional "?" -> ValueError(f"alternative {a} is empty")
   - otherwise clauses left to right; the first invalid one ->
     ValueError(f"alternative {a}, clause {c}: invalid clause {clause!r}") where `clause` is
     the clause text after its surrounding spaces were removed.
The constraint is fully validated even when `available` is empty. If several elements of
`available` are the highest match, they are the same string; return it.

Examples:
    pick_version(["1.2.0", "1.10.0~rc1", "1.9.9", "2.0.0"], "@1.2, <2.0.0") == "1.9.9"
    pick_version(["1.2.0", "1.10.0~rc1", "1.9.9", "2.0.0"], "?@1.2, <2.0.0") == "1.10.0~rc1"
    pick_version(["0.9.0", "1.0.0~rc3"], "?>=0.9.0, <1.0.0 | 3.*") == "1.0.0~rc3"
    pick_version([], "1.*, ,2") raises ValueError("alternative 1, clause 2: invalid clause ''")
