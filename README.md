# code-benchmarks

In-house execution-graded Python code benchmark (48 problems, 6 categories x 8) used to
compare models for coding tasks. Rebuilt in September 2026 as **v4** after the July runners
were lost; problems and every stored model output come from the Braintrust project
`code-benchmarks`, and this repo now persists the test suite so it cannot be lost again.

- `data/problems/code-bench-v2.json` — the 48 problems (prompt, entry point, canonical solution)
- `tests/<slug>.json` — v4 test cases; `expected` values are generated from the canonical solution
- `tests/strict/<slug>.json` — **v4-strict** suite: the v4 cases (`v4:*`) plus seeded randomized,
  edge and stress cases, each problem cross-checked against an independent brute-force reference
  (specs in `codebench/strict/<category>.py`, built by `codebench/build_strict.py`)
- `data/outputs/` — model outputs (July v1/v2/v2r/v3 from Braintrust, v4 fresh runs)
- `codebench/harness.py` — sandboxed execution + scoring (checker / tests_ratio / pass)
- `codebench/build_tests.py` — author tests, fill expected values
- `codebench/calibrate.py` — agreement of the v4 suite with the stored July scores
- `codebench/generate.py` — fresh generations (Anthropic API / OpenRouter), refusals tracked
- `codebench/score.py`, `codebench/publish.py` — score a run, publish to Braintrust

Typical flow: `build_tests show <category>` -> write `tests/<slug>.json` -> `build_tests expect <slug>`
-> `calibrate --category <c>` -> `generate` -> `score --write` -> `publish`.

v4-strict: `python -m codebench.build_strict build all` regenerates `tests/strict/` (cross-check
brute vs canonical on >=500 seeded inputs, expected values from the canonical, canonical must pass
100%); score with `python -m codebench.score data/outputs/code-bench-v4__*.json --tests strict`
(`--tests v4` is the default); `python -m codebench.build_strict flips all` lists pass->fail flips.

## Hard tier (`code-bench-hard-v1`)

The v4 suite saturated (several models at 48/48), so a 32-problem hard tier was added:
8 categories x 4 (algorithms, state_machines, spec_compliance, parsing, performance,
numeric, data_structures, bug_fixing). Every command takes `--suite hard-v1`; without
it everything behaves exactly as before (v4).

- `data/problems/code-bench-hard-v1.json` — assembled problems (ids `hard-<slug>`, same schema as v2)
- `tests/hard/<slug>.json` — tests; `stress_*` cases carry tight `timeout_s`
- `data/problems/hard-refs/<slug>/` — source of truth per problem: `prompt.md`, `canonical.py`,
  independent `brute.py`, random-input `gen.py`, and `naive.py` (correct but slow) where speed matters
- `data/problems/hard-refs/_results/` — recorded cross-check / naive / timing / self-check results
- `codebench/hard_tools.py` — `assemble`, `build` (fill expected from canonical), `crosscheck`,
  `naive`, `timing`, `selfcheck`

Run a model on the hard tier:

    export CODEBENCH_PYTHON=/opt/homebrew/bin/python3.12
    uv run --python 3.12 python -m codebench.generate --suite hard-v1 --provider openrouter \
        --model <model> --key-file <key> --tag <tag> [--max-cost-usd 5]
    uv run --python 3.12 python -m codebench.score data/outputs/code-bench-hard-v1__<tag>.json --write --verbose
    uv run --python 3.12 python -m codebench.harness --suite hard-v1     # canonical self-check

Hard-tier generations default to `max_tokens` 65536 (v4 keeps 16384; `CODEBENCH_MAX_TOKENS`
overrides both) because a 16k smoke run truncated half the answers. Answers cut off by the token
limit are recorded as `truncated` failures, not refusals.
