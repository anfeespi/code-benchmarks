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
