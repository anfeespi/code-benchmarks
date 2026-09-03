"""Render the v4 readout as a Bedrock-style HTML report (English). PDF via Chrome headless.
Usage: python -m codebench.report reports/code-bench-v4.html
"""
import collections
import html
import json
import statistics
import sys
from datetime import date

from .harness import ROOT, load_problems

MODELS = [("grok-4.5", "Grok 4.5", "OpenRouter"), ("gemini-3.8-flash", "Gemini 3.8 Flash", "OpenRouter"),
          ("fable-5.1", "Claude Fable 5.1", "Anthropic API"), ("kimi-k3", "Kimi K3", "OpenRouter"),
          ("glm-5.2", "GLM 5.2", "OpenRouter"), ("opus-5", "Claude Opus 5", "Anthropic API"), ("fable-5", "Claude Fable 5", "Anthropic API")]
LIST_PRICE = {"fable-5.1": (10, 50), "fable-5": (10, 50), "opus-5": (5, 25)}  # USD per M tokens; direct API returns no cost
CATS = [("algorithms", "Algorithms"), ("data_structures", "Data structures"), ("optimization", "Optimization"),
        ("bug_fixing", "Bug fixing"), ("spec_compliance", "Spec compliance"), ("edge_cases", "Edge cases")]
def july_pass(tag):
    f = ROOT / "data" / "outputs" / ("code-bench-v4-july__%s.json" % tag)
    return sum(r["scores"]["pass"] for r in json.load(open(f))) if f.exists() else None

e = html.escape


def load(tag):
    return json.load(open(ROOT / "data" / "outputs" / ("code-bench-v4__%s.json" % tag)))


def main(out):
    probs = {p["title"]: p for p in load_problems()}
    stats, grid, fails = {}, {}, {}
    for tag, name, src in MODELS:
        rows = load(tag)
        g = {c: [0, 0] for c, _ in CATS}
        att = []
        f = []
        for r in rows:
            p = probs[r["title"]]
            empty = not (r["code"] or "").strip()
            g[p["category"]][0] += r["scores"]["pass"]
            g[p["category"]][1] += int(empty)
            if not empty:
                att.append(r)
                if not r["scores"]["pass"]:
                    f.append((p["category"], p["slug"], (r.get("detail") or ["?"])[0]))
        n_pass = sum(v[0] for v in g.values())
        n_empty = sum(v[1] for v in g.values())
        # July rows carry no stop_reason: per the July 25 run notes, Claude 5 empties are API refusals, GLM empties hit max_tokens
        refusal = any((r.get("metadata") or {}).get("stop_reason") == "refusal" for r in rows)
        stats[tag] = dict(name=name, src=src, n_pass=n_pass, n_empty=n_empty, empty_kind="refusals" if refusal else ("output cap" if n_empty else ""),
                          att=len(att), acc=100 * n_pass / len(att) if att else 0,
                          lat=statistics.mean((r["metadata"].get("latency_s") or 0) for r in att) if att else 0,
                          tok=statistics.mean((r["metadata"].get("tokens_out") or 0) for r in att) if att else 0,
                          cost=(sum(((r["metadata"].get("tokens_in") or 0) * LIST_PRICE[tag][0] + (r["metadata"].get("tokens_out") or 0) * LIST_PRICE[tag][1]) / 1e6 for r in rows)
                                if tag in LIST_PRICE else sum((r["metadata"].get("cost_usd") or 0) for r in rows)), est=tag in LIST_PRICE)
        grid[tag] = g
        fails[tag] = f
    rows_html = "".join(
        "<tr><td>%s</td><td class=n>%d/48 (%.0f%%)</td><td class=n>%.0f%%</td><td class=n>%s</td><td class=n>%.1f s</td><td class=n>%s</td><td class=n>%s</td><td class=note>%s</td></tr>" % (
            e(s["name"]), s["n_pass"], 100 * s["n_pass"] / 48, s["acc"],
            ("%d %s" % (s["n_empty"], s["empty_kind"])) if s["n_empty"] else "0", s["lat"], "{:,.0f}".format(s["tok"]),
            (("≈" if s["est"] else "") + "$%.2f" % s["cost"]) if s["cost"] else "n/a", e(s["src"])) for tag, s in ((t, stats[t]) for t, _, _ in MODELS))
    matrix = "".join("<tr><td>%s</td>%s</tr>" % (e(cn), "".join(
        "<td class=n>%s</td>" % ("<span class=ref>%d refused</span>" % grid[t][c][1] if grid[t][c][0] == 0 and grid[t][c][1] else
                                 ("%d/8" % grid[t][c][0] + (" <span class=ref>(%d✕)</span>" % grid[t][c][1] if grid[t][c][1] else "")))
        for t, _, _ in MODELS)) for c, cn in CATS)
    mhead = "".join("<th class=n>%s</th>" % e(n.replace("Claude ", "")) for _, n, _ in MODELS)
    july_rows = "".join("<tr><td>%s</td><td class=n>%d/48</td><td class=n>%d/48</td><td class=n>%+d</td></tr>" % (
        e(stats[t]["name"]), july_pass(t), stats[t]["n_pass"], stats[t]["n_pass"] - july_pass(t)) for t, _, _ in MODELS if july_pass(t) is not None)
    fail_rows = "".join("<tr><td>%s</td><td>%s</td><td class=mono>%s</td><td class=note>%s</td></tr>" % (
        e(stats[t]["name"]), e(c), e(slug), e(d[:150])) for t, _, _ in MODELS for c, slug, d in fails[t])
    css = """<style>
@page{size:letter;margin:20mm 20mm}
body{font:10.5pt/1.5 "Helvetica Neue",Helvetica,Arial,sans-serif;color:#1c1e22;margin:0}
.head{display:flex;justify-content:space-between;align-items:baseline;border-bottom:2pt solid #1c1e22;padding-bottom:2.5mm;margin-bottom:6mm}
.head .who{font-size:8.5pt;color:#7a7d85;text-align:right}
h1{font-size:17pt;font-weight:700;letter-spacing:-.01em;margin:0;line-height:1.2}
.verdict{background:#eef6f0;border-left:3pt solid #1f7a4d;padding:3.5mm 5mm;margin:0 0 6mm;font-size:11pt}
.verdict b{color:#1f7a4d}
h2{font-size:11.5pt;font-weight:700;margin:6mm 0 2mm}
h3{font-size:10.5pt;font-weight:700;margin:4mm 0 1.5mm}
p{margin:0 0 2.5mm;max-width:46em}
ul{margin:0 0 2.5mm 5mm;padding:0;max-width:46em} li{margin:0 0 1mm}
table{border-collapse:collapse;width:100%;margin:2mm 0 3mm;font-variant-numeric:tabular-nums}
th{font-size:8pt;text-transform:uppercase;letter-spacing:.06em;color:#7a7d85;text-align:left;padding:1.6mm 3mm;border-bottom:1pt solid #1c1e22}
td{padding:1.6mm 3mm;border-bottom:.4pt solid #d9dade;font-size:9.8pt;vertical-align:top}
td.n,th.n{text-align:right}
.mono{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-size:9pt}
.note{font-size:8.8pt;color:#7a7d85}
.ref{color:#b3412a;font-size:8.8pt}
.foot{margin-top:7mm;padding-top:2.5mm;border-top:.5pt solid #d9dade;font-size:8pt;color:#7a7d85}
.pb{page-break-before:always}
</style>"""
    g51, gg = stats["fable-5.1"], stats["gemini-3.8-flash"]
    body = """<!doctype html><html><head><meta charset="utf-8"><title>Code benchmark v4 — seven models</title>%s</head><body>
<div class=head><h1>Yuno code benchmark v4 — seven models, one baseline</h1><div class=who>AI Squad · Yuno<br>%s</div></div>
<div class=verdict><b>Verdict.</b> Seven models regenerated on the same day, same protocol, same rebuilt suite. <b>Grok 4.5 and Gemini 3.8 Flash pass 48/48</b>; Gemini is the cheapest run ($%.2f) and twice as fast as Grok. <b>Claude Fable 5.1 passes 40/48</b>: it refuses %d prompts (optimization and algorithms) and is <b>100%% correct on everything it attempts</b>. Kimi K3 (40) and GLM 5.2 (35) lose answers by exhausting the 16k output cap on reasoning; Opus 5 and Fable 5 (35 each) refuse 13 and are perfect on the rest. The Claude 5 raw-API refusal remains the operational risk, but it moved from 30/48 (Fable 5, July) to 8/48 (Fable 5.1).</div>
<h2>What was tested</h2>
<p>48 in-house HumanEval-style Python problems in six categories (algorithms, data structures, optimization, bug fixing, spec compliance, edge cases; 8 each). Each model receives the problem prompt as the only user message, no system prompt (Claude: no temperature; OpenRouter models: temperature 0). Grading is by execution: the candidate module is imported in a sandboxed child process (memory and time limits) and run against the test cases; <span class=mono>pass</span> requires every case, <span class=mono>tests_ratio</span> is the fraction passed, <span class=mono>checker</span> is 1 when the module loads and defines the entry point. Refusals (<span class=mono>stop_reason: refusal</span>) and empty answers score 0 and are reported separately so they are never confused with wrong code.</p>
<p><b>The v4 suite.</b> Both July runners were lost, so the suite was rebuilt from the problems and canonical solutions stored in Braintrust: 461 cases (6-15 per problem), expected values generated by executing the canonical solution, and a large deterministic input per optimization problem sized so a quadratic solution times out while the canonical runs in under a second. The suite was calibrated against the stored July 25 outputs of five models: 89.6%% agreement on pass (215/240). Every disagreement was reviewed: 21 go in the model's favour (July tests stricter than the prompt; the outputs are behaviourally identical to the canonical under fuzzing) and 4 are real bugs July missed. Candidates run on Python 3.12 (the prompts never pin a version; on 3.9 two correct Gemini solutions failed on <span class=mono>int | None</span> and <span class=mono>bisect(key=)</span>). The suite, harness and every output now live in the <span class=mono>code-benchmarks</span> repository.</p>
<p><b>One baseline.</b> All seven models were generated on September 2 with a 16,384-token output cap. Two kinds of empty answer are reported separately: the Anthropic API classifier refusing a benign prompt (<span class=mono>stop_reason: refusal</span>) and a reasoning model exhausting the output cap without emitting code (<span class=mono>finish_reason: length</span>; retrying at 32k changed nothing, the provider caps Kimi and GLM at 16,384). Two Opus 5 requests hit 529 Overloaded and were retried successfully.</p>
<h2>Results</h2>
<table><tr><th>model</th><th class=n>pass (raw)</th><th class=n>when attempted</th><th class=n>empty</th><th class=n>latency</th><th class=n>output tokens</th><th class=n>cost / run</th><th>source</th></tr>%s</table>
<p class=note>Empty = API refusal (Claude 5) or output cap exhausted by reasoning (Kimi, GLM). "When attempted" = passes ÷ answered prompts. Latency and tokens are per-problem means on answered prompts. Cost per 48-problem run: measured by OpenRouter; ≈ list-price estimate (tokens × rate) for the direct Anthropic API.</p>
<h3>By category (passes out of 8)</h3>
<table><tr><th>category</th>%s</tr>%s</table>
<h3>July 25 outputs vs September 2 outputs, both scored on v4</h3>
<table><tr><th>model</th><th class=n>Jul 25 generation</th><th class=n>Sep 2 generation</th><th class=n>Δ</th></tr>%s</table>
<p class=note>Same suite, same scoring; only the generation date differs. Fable 5 gains 19 problems purely from fewer refusals (30 → 13) on identical prompts; Kimi and GLM lose problems to longer reasoning that now exhausts the output cap; Grok fixes the two cases its July code got wrong.</p>
<div class=pb></div>
<h2>Findings</h2>
<ul>
<li><b>Grok 4.5 and Gemini 3.8 Flash clear the whole suite.</b> Both 48/48 with no empty answers. Gemini does it at $%.2f and %.1f s per problem (%.0f output tokens); Grok takes 45.8 s per problem, twice its July pace, with longer answers (2.6k tokens). Grok also fixes the two cases its July outputs got wrong (FIFO scheduler re-submission, <span class=mono>str.format</span> where forbidden).</li>
<li><b>Fable 5.1 attempts far more and never misses.</b> 8 refusals (5 optimization, 3 algorithms; the other four categories are 8/8) and 40/40 on what it answers, with the shortest answers in the set (%.0f tokens, %.1f s). Fable 5 itself, regenerated today, refuses 13 instead of July's 30 on identical prompts: the classifier moved on Anthropic's side, and the model is 35/35 when it answers. Opus 5: 13 refusals, 35/35.</li>
<li><b>Reasoning models hit the output cap.</b> Kimi K3 leaves 6 problems and GLM 5.2 leaves 12 with no code after 16,384 output tokens of reasoning; retrying with a 32k budget changed nothing because the provider caps both there. On what they deliver they are strong (Kimi 40/42, GLM 35/36), but Kimi is now the most expensive run ($4.09) and, with Grok, the slowest.</li>
<li><b>Two empties, one score.</b> A refusal and an exhausted cap both score 0 like a wrong answer and are invisible unless <span class=mono>stop_reason</span> / <span class=mono>finish_reason</span> is inspected. Every Claude 5 refusal in this suite came from bare code prompts over the raw API; the Maia agent evals run on Fable without a single refusal.</li>
</ul>
<h2>Recommendation</h2>
<p>For autonomous code agents on the raw API, Gemini 3.8 Flash and Grok 4.5 are the frictionless choices; Gemini wins on cost and latency. Fable 5.1 is viable where a supervising loop can detect a refusal and re-route (its accuracy is the best in the set), and refusal rates should be re-measured on every release: Fable 5 went from 30 to 13 refusals in five weeks with no version change. Give reasoning models (Kimi, GLM) a larger output budget where the provider allows it, or expect empty answers on the hardest prompts. Keep the suite in the repository and re-run <span class=mono>calibrate</span> before every comparison.</p>
<h2>Appendix — non-refusal failures per model</h2>
<table><tr><th>model</th><th>category</th><th>problem</th><th>first failing case</th></tr>%s</table>
<div class=foot>Sources: Braintrust project "code-benchmarks", experiments code-bench-v4__* (seven models regenerated 2026-09-02, 48 rows each, first failing test in metadata) and code-bench-v4-july__* (July 25 outputs re-scored); repository code-benchmarks (harness, tests, outputs, this report). Prepared by Andrés Espitia with Claude Code.</div>
</body></html>""" % (css, date.today().isoformat(), gg["cost"] or 0, g51["n_empty"], rows_html, mhead, matrix, july_rows,
                     gg["cost"] or 0, gg["lat"], gg["tok"], g51["tok"], g51["lat"], fail_rows)
    open(out, "w").write(body)
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1])
