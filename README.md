# code-benchmarks

Yuno's in-house benchmark for comparing models on coding work. Every answer is executed
and graded by tests; nothing is judged by another model.

There are three suites. They share one idea: give the model a problem, save what it
answered, run its code against tests.

| Suite | What it measures | Size |
|---|---|---|
| `v4` | Single Python functions across 6 categories | 48 problems |
| `hard-v1` | Harder Python problems, added when `v4` saturated | 32 problems |
| `agentic-go-v1` | Ticket-style work with tools in a Go payments service | 18 tasks |

## Results

Problems passed on the first attempt. A refusal or an answer cut off by the output limit
counts as a failure. `v4 strict` is the same 48 problems under a larger test set.

| Model | v4 | v4 strict | hard-v1 | agentic-go-v1 |
|---|---|---|---|---|
| Claude Fable 5.2 | 48/48 | 48/48 | 32/32 | 18/18 |
| Claude Sonnet 5.5 | 48/48 | 48/48 | 30/32 | 18/18 |
| Grok 4.5 | 48/48 | 48/48 | 25/32 | 18/18 |
| Gemini 3.8 Flash | 48/48 | 48/48 | 14/32 | 17/18 |
| GPT 6.1 Sol | 47/48 | 46/48 | 32/32 | 18/18 |
| Claude Opus 5.5 | 46/48 | 46/48 | 30/32 | 18/18 |
| Gemini 4 Argon | 46/48 | 46/48 | 27/32 | 18/18 |
| Claude Fable 5.1 | 40/48 | 39/48 | 31/32 | 18/18 |
| Kimi K3 | 40/48 | 40/48 | 24/32 | 18/18 |
| GLM 5.2 | 35/48 | 35/48 | 9/32 | 18/18 |
| Claude Opus 5 | 35/48 | 35/48 | not run | not run |
| Claude Fable 5 | 35/48 | 34/48 | not run | not run |

Reading notes:

- Most `v4` failures of Claude Fable 5.1, Fable 5 and Opus 5 are refusals (8, 13 and 13), not wrong code.
- Kimi K3 and GLM 5.2 lose problems to empty or truncated answers at the provider's output limit.
  The same happens to Gemini 3.8 Flash on `hard-v1` (16 truncated).
- Claude Fable 5.1 ran `v4` on the Anthropic API and the other two suites on Bedrock.
- `agentic-go-v1` is saturated: it no longer separates models on pass rate, only on cost and time.
  Per-run cost, tool calls and wall time are in `data/agentic/outputs/`.

## Run a model

Requires Python 3.12, [uv](https://docs.astral.sh/uv/) and, for the agentic suite, Go 1.22+.
Put the provider key in a file; it is never read from the command line.

```bash
export CODEBENCH_PYTHON=/opt/homebrew/bin/python3.12   # interpreter that runs the candidates
RUN="uv run --python 3.12 --with requests --with anthropic --with boto3 python -m"

# 1. generate: one answer per problem, saved to data/outputs/<suite>__<tag>.json
$RUN codebench.generate --suite v4 --provider openrouter --model google/gemini-4-argon \
    --tag gemini-4-argon --key-file /tmp/openrouter-key.txt --max-cost-usd 5

# 2. score: run every answer in the sandbox and store the result in the same file
$RUN codebench.score data/outputs/code-bench-v4__gemini-4-argon.json --write --verbose
$RUN codebench.score data/outputs/code-bench-v4__gemini-4-argon.json --tests strict

# same two steps for the hard suite
$RUN codebench.generate --suite hard-v1 --provider openrouter --model google/gemini-4-argon \
    --tag gemini-4-argon --key-file /tmp/openrouter-key.txt --max-cost-usd 5
$RUN codebench.score data/outputs/code-bench-hard-v1__gemini-4-argon.json --write --verbose

# agentic suite: generates and grades in one command
$RUN codebench.agentic run --provider openrouter --model google/gemini-4-argon \
    --tag gemini-4-argon --key-file /tmp/openrouter-key.txt
```

Providers: `openrouter`, `anthropic` (both with `--key-file`) and `bedrock`
(`--aws-profile`, `--region`, model given as an inference profile id such as
`global.anthropic.claude-sonnet-5-5`).

Optional last steps: `codebench.publish` uploads a scored run to the Braintrust project
`code-benchmarks`, and `codebench.report reports/code-bench-v4.html` renders the v4 readout.
`reports/` is local output and is not tracked.

## How grading works

- Each problem has a prompt, an entry point and a canonical solution.
- Each test case is an input plus the expected value, and the expected value is produced by
  running the canonical solution. Tests are data, not code.
- `codebench/harness.py` runs the candidate in a subprocess with a timeout per case and
  compares outputs. A problem passes only if every case passes.
- Per problem the score file keeps `pass`, `tests_ratio` (share of cases passed) and `checker`.
- A refusal, an empty answer and a truncated answer are recorded as such in `metadata`, so
  "wrong" and "did not answer" can be told apart.

## The suites in detail

### v4

- Problems: `data/problems/code-bench-v2.json` (the file name is historical; this is the v4 problem set).
- Categories, 8 problems each: algorithms, data structures, optimization, bug fixing,
  spec compliance, edge cases.
- Tests: `tests/<slug>.json`, 461 cases in total.
- Strict tests: `tests/strict/<slug>.json`. The v4 cases plus seeded random, edge and stress
  cases. Each problem is cross-checked against an independent brute-force reference in
  `codebench/strict/<category>.py`.

### hard-v1

- Problems: `data/problems/code-bench-hard-v1.json`, assembled from `data/problems/hard-refs/<slug>/`.
  Each folder holds `prompt.md`, `canonical.py`, an independent `brute.py`, a random-input
  `gen.py`, and `naive.py` (correct but slow) where speed is part of the problem.
- Categories, 4 problems each: algorithms, state machines, spec compliance, parsing,
  performance, numeric, data structures, bug fixing.
- Tests: `tests/hard/<slug>.json`. `stress_*` cases carry a tight `timeout_s`.
- Generations default to `max_tokens` 65536 (v4 uses 16384; `CODEBENCH_MAX_TOKENS` overrides both).

### agentic-go-v1

- `agentic/go-payments/`: a small Go service (money and rounding, payment state machine with
  partial refunds, idempotency store, webhook dispatcher with retries, HTTP API) with visible tests.
- `agentic/tasks/<id>/`: `task.json` (the ticket), `start.patch` (starting state),
  `solution.patch` (reference fix) and `hidden/` (acceptance tests the model never sees).
- `codebench/agentic.py`: the tool loop (`list_files`, `read_file`, `write_file`, `apply_edit`,
  `run` limited to `go build/test/vet` and `gofmt`, `finish`) with a budget of 40 tool calls
  and 150k tokens of context.
- A task passes when `go test -race -count=1 ./...` passes with the hidden tests, no visible
  test was broken, and `go vet` and `gofmt` are clean.
- Outputs: `data/agentic/outputs/agentic-go-v1__<tag>.json` (per-task result, tokens, cost, time)
  and `data/agentic/runs/<tag>/<task>.jsonl` (full transcripts).

## Maintaining the suites

These commands build or verify the benchmark itself; you do not need them to run a model.

```bash
$RUN codebench.harness                      # v4: every canonical solution passes its tests
$RUN codebench.harness --suite hard-v1      # same for the hard suite
$RUN codebench.build_tests show <category>  # v4: inspect problems while authoring tests
$RUN codebench.build_tests expect <slug>    # v4: fill expected values from the canonical
$RUN codebench.build_strict build all       # regenerate tests/strict (brute vs canonical cross-check)
$RUN codebench.build_strict flips all       # list answers that pass v4 but fail strict
$RUN codebench.hard_tools selfcheck         # hard: assemble, build, crosscheck, naive, timing
$RUN codebench.agentic verify               # agentic: solutions pass, starting states fail
```

## Layout

```
codebench/        generate, score, harness, report, publish, agentic loop, suite builders
data/problems/    problem sets and the hard-suite reference solutions
data/outputs/     one file per suite and model: answers, scores, metadata
data/agentic/     agentic outputs and transcripts
tests/            v4 cases, tests/strict/ and tests/hard/
agentic/          the Go service and its 18 tasks
```
