Write a Python function:

    def evaluate_access(rules, requests) -> list[str]

It evaluates access requests against a list of textual policy rules and returns one decision
string per request.

RULES
`rules` is a list of strs. Rule `i` (0-based index in the list) is split into fields exactly
like Python's `rule.split()` (no arguments: runs of whitespace, leading/trailing ignored) and
must have exactly 4 fields: `EFFECT PRINCIPAL ACTION RESOURCE`.
- EFFECT: exactly "ALLOW" or "DENY" (case-sensitive).
- PRINCIPAL: "*" (anyone), "user:NAME" or "group:NAME", where NAME is one or more characters
  from [a-z0-9_] (ASCII).
- ACTION: "*" (any action) or a comma-separated list of one or more action words, each word
  one or more characters from [a-z] (ASCII), e.g. "read" or "read,write" (no spaces, no empty
  items, "*" cannot appear inside a list).
- RESOURCE: "/" (the root, zero segments) or "/" followed by one or more segments separated
  by "/" (so no empty segment and no trailing "/"), each segment being either "*", "**", or
  one or more characters from [a-z0-9._-]. "*" matches exactly one path segment; "**" matches
  zero or more consecutive path segments; any other segment matches only itself.

REQUESTS
`requests` is a list of 4-tuples `(user, groups, action, path)`: `user` is a NAME, `groups` is
a list of NAMEs (possibly empty), `action` is one action word, and `path` is "/" or "/"
followed by one or more "/"-separated segments of [a-z0-9._-]+ (no wildcards).

VALIDATION (complete before any evaluation; the first failure raises)
1. `rules` not a list -> TypeError("rules must be a list")
2. `requests` not a list -> TypeError("requests must be a list")
3. Every rule, in index order; for rule i the checks are, in order:
   not a str -> TypeError(f"rule {i}: not a str");
   field count != 4 -> ValueError(f"rule {i}: expected 4 fields, got {count}");
   bad EFFECT -> ValueError(f"rule {i}: bad effect {effect!r}");
   bad PRINCIPAL -> ValueError(f"rule {i}: bad principal {principal!r}");
   bad ACTION -> ValueError(f"rule {i}: bad action {action!r}");
   bad RESOURCE -> ValueError(f"rule {i}: bad resource {resource!r}").
4. Then every request, in index order; for request j:
   not a tuple of length 4 -> TypeError(f"request {j}: expected 4-tuple");
   user not a str NAME -> ValueError(f"request {j}: bad user {user!r}");
   groups not a list, or any element not a str NAME -> ValueError(f"request {j}: bad groups");
   action not a str action word -> ValueError(f"request {j}: bad action {action!r}");
   path not a valid str path -> ValueError(f"request {j}: bad path {path!r}").

EVALUATION of one request: a rule MATCHES when all of these hold:
- PRINCIPAL is "*", or is "user:U" with U == user, or is "group:G" with G in groups;
- ACTION is "*" or its list contains the request's action;
- RESOURCE matches the whole path (all path segments consumed).
Each matching rule has a SPECIFICITY, the tuple (L, P, A) compared lexicographically, larger
is more specific:
- L = number of RESOURCE segments that are neither "*" nor "**";
- P = 2 for "user:...", 1 for "group:...", 0 for "*";
- A = 1 for an action list, 0 for "*".
Only the matching rules with the maximal specificity are considered. If any of them is a DENY,
the decision is f"DENY by rule {i}" for the smallest index i among those DENY rules;
otherwise it is f"ALLOW by rule {i}" for the smallest index among them. If no rule matches,
the decision is "DENY by default".

Return the list of decisions in request order (an empty `requests` gives []).

Input sizes: up to 500 rules, 5,000 requests, paths of up to 50 segments, and resources with
up to 10 "**" segments; resource matching must not take exponential time (e.g. naive
backtracking over several "**" segments is too slow).

Examples:
    rules = ["ALLOW group:eng read,write /repos/**",
             "DENY  *         *          /repos/*/secrets/**",
             "ALLOW user:ann  read       /repos/core/secrets/**",
             "ALLOW group:eng *          /repos/*/secrets/**",
             "DENY  group:ops *          /repos/*/secrets/**"]
    evaluate_access(rules, [("bob", ["eng"], "read", "/repos/core/src/main.py"),
                            ("ann", ["eng"], "read", "/repos/core/secrets/key"),
                            ("bob", ["eng"], "read", "/repos/core/secrets/key"),
                            ("bob", ["eng", "ops"], "read", "/repos/core/secrets/key"),
                            ("bob", [], "read", "/repos/core/secrets"),
                            ("bob", [], "read", "/")])
    == ["ALLOW by rule 0", "ALLOW by rule 2", "ALLOW by rule 3", "DENY by rule 4",
        "DENY by rule 1", "DENY by default"]
    # request 2: rules 0 (1,1,1), 1 (2,0,0) and 3 (2,1,0) match; rule 3 is the most specific.
    # request 3: rules 3 and 4 tie at (2,1,0) and rule 4 is a DENY.
    # request 4: "**" matches zero segments, so only rule 1 matches.

    evaluate_access(["ALLOW * read /a"], [("x", [], "Read", "/a")])
        raises ValueError("request 0: bad action 'Read'")
