Write a Python function:

    def run_pile(src: str, max_steps: int) -> tuple

that checks and runs a program in the stack language "Pile". It never raises: it returns
`("ok", stack)` or `("error", token_index, message)`, where `token_index` is the 0-based
index of a token in the token list of `src` and `message` is one of the exact strings below.

TOKENS. The whitespace characters are exactly ' ', '\t', '\n', '\r'; every other character
(including other Unicode spaces) is ordinary. '[' and ']' are always single-character tokens,
even when glued to other characters ("[1" is the tokens "[" and "1"). Every other token is a
maximal run of characters that are neither whitespace nor '[' / ']'. Tokens are numbered
0, 1, 2, ... in order. A token is an INT if it matches  -?[0-9]+  (ASCII digits only;
"007" is 7, "-0" is 0, "+5" and "--1" are not INTs). The tokens ":" and ";" are special
(only when they are the entire token; "a:b" and "x;" are ordinary words). Any other token
is a WORD.

STRUCTURE CHECK (done before running anything). Scan the tokens left to right with a stack
of open constructs:
- "[" opens a quotation.
- "]" closes the innermost open construct, which must be a "[", otherwise (nothing open,
  or the innermost open construct is a definition) error "unmatched ]" at the "]".
- ":" starts a definition. If any construct is open: error "misplaced :" at the ":".
  If ":" is the last token: error "unclosed :" at the ":". The next token is the NAME
  (it is consumed here and not otherwise scanned); if it is "[", "]", ":", ";", an INT or
  a builtin name (listed below): error "bad name" at the NAME's index.
- ";" closes the innermost open construct, which must be a ":" definition, otherwise
  error "unmatched ;" at the ";".
- If constructs are still open at the end: error "unclosed [" or "unclosed :" at the
  EARLIEST (smallest index) still-open "[" or ":".
The first error in this scan is returned. So definitions only appear at top level and
contain balanced quotations; quotations never contain ":" or ";".

VALUES are ints (unbounded) and quotations. A quotation is the token sequence between a
"[" and its matching "]".

EXECUTION. The top-level token sequence is executed element by element. An ELEMENT is
a whole quotation "[ ... ]" (index = its "["), a whole definition ": NAME ... ;" (index =
its ":"), or a single other token. Executing a sequence executes its elements in order.
Before executing ANY element, one step is consumed; if the total number of steps would
exceed `max_steps`, stop with error "step limit exceeded" at that element (it is not
executed). Then:
- INT: push it.
- Quotation: push it (its body is NOT executed now).
- Definition: (re)define NAME as the body token sequence between NAME and ";". Words are
  looked up when executed, so a body may call words defined later, including itself, and
  a later definition of the same NAME replaces the earlier one from then on.
- WORD that is a builtin: run the builtin (below).
- Other WORD currently defined: execute its body sequence.
- Other WORD: error "unknown word 'WORD'" at it.
Elements inside quotations and definition bodies keep their own token indexes, so
errors raised inside them point inside them.

BUILTINS. Stack notation: `a b -- r` means b is the top before, r is pushed after.
  dup  a -- a a         drop a --            swap a b -- b a
  over a b -- a b a     rot  a b c -- b c a
  +  -  *   a b -- a+b / a-b / a*b
  /  %      a b -- a//b / a%b  (Python floor division and modulo)
  <  =      a b -- 1 if a<b (resp. a==b) else 0
  if    c t f --    executes quotation t if c != 0, else quotation f
  times q n --      executes quotation q n times
  while c b --      repeatedly: execute quotation c, then pop the top value v (it must
                    exist and be an int); if v != 0 execute quotation b and repeat,
                    otherwise stop
  call  q --        executes quotation q
  dip   a q --      removes a, executes quotation q, then pushes a back
Checks for a builtin, in this order, all reported at the builtin's token index:
1. "stack underflow" if the stack holds fewer values than the builtin takes (1 for dup,
   drop, call; 3 for rot, if; 2 for all others).
2. "type error" if an operand has the wrong type: + - * / % < = need two ints; if needs
   an int c and quotations t and f; times needs a quotation q and an int n; while needs
   two quotations; call needs a quotation; dip needs q to be a quotation (a may be
   anything). dup/drop/swap/over/rot accept anything.
3. "division by zero" (/ or % with b == 0); "negative count" (times with n < 0).
The operands are removed before the quotation(s) run. In `while`, a missing or non-int v
after running c is "stack underflow" / "type error" at the `while` token.
Executing an empty quotation consumes no steps (so `[ ] 1000000000 times` is instant).

RESULT. On success return ("ok", stack) listing the stack bottom to top; ints are ints and
a quotation is shown as a list of its elements: nested quotations as nested lists and every
other token as its string (e.g. "[ 1 [ dup ] x ]" is ["1", ["dup"], "x"]).

Programs can be long (up to 10**6 tokens), quotations can be nested up to 50,000 deep,
user words can recurse up to 100,000 levels deep, and `max_steps` can be up to 3*10**6.
Mind Python's recursion limit, and keep the per-step cost small: a run of 3*10**6 steps
must finish in a few seconds.

Examples:
- run_pile(": sq dup * ;  3 sq [ 1 [ dup ] ] 10 [ 2 ] dip", 100)
      == ("ok", [9, ["1", ["dup"]], 2, 10])
- run_pile(": fact dup 1 < [ drop 1 ] [ dup 1 - fact * ] if ; 5 fact", 1000) == ("ok", [120])
- run_pile("1 2 + dup", 3) == ("error", 3, "step limit exceeded")
- run_pile("5 [ 1 - ] 3 times 0 [ drop ] if", 100) == ("error", 11, "type error")
  # after `times` the stack is [2]; `if` gets c=2, t=0, f=[ drop ]
- run_pile("1 [ 2 ] ] [", 100) == ("error", 4, "unmatched ]")
- run_pile("[ [ ] : g", 100) == ("error", 3, "misplaced :")
