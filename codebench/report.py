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

MODELS = [("gemini-3.8-flash", "Gemini 3.8 Flash", "fresh Sep 2 · OpenRouter"), ("kimi-k3", "Kimi K3", "Jul 25 outputs re-scored"),
          ("grok-4.5", "Grok 4.5", "Jul 25 outputs re-scored"), ("glm-5.2", "GLM 5.2", "Jul 25 outputs re-scored"),
          ("fable-5.1", "Claude Fable 5.1", "fresh Sep 2 · Anthropic API"), ("opus-5", "Claude Opus 5", "Jul 25 outputs re-scored"),
          ("fable-5", "Claude Fable 5", "Jul 25 outputs re-scored")]
CATS = [("algorithms", "Algorithms"), ("data_structures", "Data structures"), ("optimization", "Optimization"),
        ("bug_fixing", "Bug fixing"), ("spec_compliance", "Spec compliance"), ("edge_cases", "Edge cases")]
JULY = {"kimi-k3": 42, "grok-4.5": 43, "glm-5.2": 39, "opus-5": 32, "fable-5": 15}  # v3 pass counts, Jul 25

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
        refusal = any((r.get("metadata") or {}).get("stop_reason") == "refusal" or (r.get("metadata") or {}).get("refused") for r in rows if not (r["code"] or "").strip())
        stats[tag] = dict(name=name, src=src, n_pass=n_pass, n_empty=n_empty, empty_kind="refusals" if refusal else ("max_tokens" if n_empty else ""),
                          att=len(att), acc=100 * n_pass / len(att) if att else 0,
                          lat=statistics.mean((r["metadata"].get("latency_s") or 0) for r in att) if att else 0,
                          tok=statistics.mean((r["metadata"].get("tokens_out") or 0) for r in att) if att else 0,
                          cost=sum((r["metadata"].get("cost_usd") or 0) for r in rows) or None)
        grid[tag] = g
        fails[tag] = f
    rows_html = "".join(
        "<tr><td>%s</td><td class=n>%d/48 (%.0f%%)</td><td class=n>%.0f%%</td><td class=n>%s</td><td class=n>%.1f s</td><td class=n>%s</td><td class=n>%s</td><td class=note>%s</td></tr>" % (
            e(s["name"]), s["n_pass"], 100 * s["n_pass"] / 48, s["acc"],
            ("%d %s" % (s["n_empty"], s["empty_kind"])) if s["n_empty"] else "0", s["lat"], "{:,.0f}".format(s["tok"]),
            ("$%.2f" % s["cost"]) if s["cost"] else "n/a", e(s["src"])) for tag, s in ((t, stats[t]) for t, _, _ in MODELS))
    matrix = "".join("<tr><td>%s</td>%s</tr>" % (e(cn), "".join(
        "<td class=n>%s</td>" % ("<span class=ref>%d refused</span>" % grid[t][c][1] if grid[t][c][0] == 0 and grid[t][c][1] else
                                 ("%d/8" % grid[t][c][0] + (" <span class=ref>(%d✕)</span>" % grid[t][c][1] if grid[t][c][1] else "")))
        for t, _, _ in MODELS)) for c, cn in CATS)
    mhead = "".join("<th class=n>%s</th>" % e(n.replace("Claude ", "")) for _, n, _ in MODELS)
    july_rows = "".join("<tr><td>%s</td><td class=n>%d/48</td><td class=n>%d/48</td><td class=n>%+d</td></tr>" % (
        e(stats[t]["name"]), JULY[t], stats[t]["n_pass"], stats[t]["n_pass"] - JULY[t]) for t in JULY)
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
<div class=head><h1>Yuno code benchmark v4 — seven models, execution-graded</h1><div class=who>AI Squad · Yuno<br>%s</div></div>
<div class=verdict><b>Verdict.</b> On the rebuilt 48-problem suite, <b>Gemini 3.8 Flash passes 48/48</b> with no friction and the cheapest run ($%.2f). <b>Claude Fable 5.1 passes 40/48</b>: it refuses %d prompts (all optimization and algorithms) but is <b>100%% correct on everything it attempts</b>, closing most of the gap left by Fable 5 (16/48, 30 refusals). Kimi K3 (47), Grok 4.5 (45) and GLM 5.2 (44) keep their July order. The Claude 5 raw-API refusal pattern is still the operational risk for autonomous code agents, but it is now 8/48 instead of 30/48.</div>
<h2>What was tested</h2>
<p>48 in-house HumanEval-style Python problems in six categories (algorithms, data structures, optimization, bug fixing, spec compliance, edge cases; 8 each). Each model receives the problem prompt as the only user message, no system prompt (Claude: no temperature; OpenRouter models: temperature 0). Grading is by execution: the candidate module is imported in a sandboxed child process (memory and time limits) and run against the test cases; <span class=mono>pass</span> requires every case, <span class=mono>tests_ratio</span> is the fraction passed, <span class=mono>checker</span> is 1 when the module loads and defines the entry point. Refusals (<span class=mono>stop_reason: refusal</span>) and empty answers score 0 and are reported separately so they are never confused with wrong code.</p>
<p><b>The v4 suite.</b> Both July runners were lost, so the suite was rebuilt from the problems and canonical solutions stored in Braintrust: 461 cases (6-15 per problem), expected values generated by executing the canonical solution, and a large deterministic input per optimization problem sized so a quadratic solution times out while the canonical runs in under a second. The suite was calibrated against the stored July 25 outputs of five models: 89.6%% agreement on pass (215/240). Every disagreement was reviewed: 21 go in the model's favour (July tests stricter than the prompt; the outputs are behaviourally identical to the canonical under fuzzing) and 4 are real bugs July missed. Candidates run on Python 3.12 (the prompts never pin a version; on 3.9 two correct Gemini solutions failed on <span class=mono>int | None</span> and <span class=mono>bisect(key=)</span>). The suite, harness and every output now live in the <span class=mono>code-benchmarks</span> repository.</p>
<h2>Results</h2>
<table><tr><th>model</th><th class=n>pass (raw)</th><th class=n>when attempted</th><th class=n>empty</th><th class=n>latency</th><th class=n>output tokens</th><th class=n>cost / run</th><th>source</th></tr>%s</table>
<p class=note>Empty = API refusal (Claude 5) or reasoning that exhausted max_tokens (GLM). "When attempted" = passes ÷ answered prompts. Latency and tokens are per-problem means on answered prompts; cost is only available through OpenRouter. The five July models are their July 25 generations re-scored under v4; Fable 5.1 and Gemini 3.8 Flash are fresh September 2 generations under the same protocol.</p>
<h3>By category (passes out of 8)</h3>
<table><tr><th>category</th>%s</tr>%s</table>
<h3>July 25 (v3) vs September 2 (v4), same outputs</h3>
<table><tr><th>model</th><th class=n>v3 pass</th><th class=n>v4 pass</th><th class=n>Δ</th></tr>%s</table>
<p class=note>v3 = the July 25 reconstructed suite (since lost). Order preserved; GLM and Opus recover cases where July tests were stricter than the prompt; Grok loses two genuine ones (see below).</p>
<div class=pb></div>
<h2>Findings</h2>
<ul>
<li><b>Fable 5.1 attempts far more and never misses.</b> 8 refusals against Fable 5's 30 on identical prompts (5 optimization, 3 algorithms; bug fixing, spec, data structures and edge cases are 8/8), and 40/40 on what it answers, with the shortest answers of the fresh runs (%.0f tokens, %.1f s). The mechanism is unchanged — the API safety classifier declines benign code prompts with an empty body — but it fires four times less often.</li>
<li><b>Gemini 3.8 Flash is the first model to clear the whole suite.</b> 48/48 at $%.2f for the run, %.1f s per problem, verbose (%.0f output tokens, second only to GLM). No refusals, no truncation.</li>
<li><b>Opus 5 remains the most accurate Claude when it answers</b> (35/35 attempted, 100%%) but still refuses 13/48; those are July 25 outputs, not re-generated here.</li>
<li><b>What v4 changed.</b> Grok 4.5 loses two real cases the July suite did not exercise: it resets a re-submitted task's version in the FIFO scheduler (served at its old position) and uses <span class=mono>str.format</span> where the prompt forbids it; Grok and Fable 5 crash with <span class=mono>TypeError</span> in the colour-graph heap on cost ties. Kimi K3's only miss is competition ranking implemented as dense ranking.</li>
<li><b>Refusal is the operational risk, not capability.</b> A refusal scores 0 like a wrong answer and is invisible unless <span class=mono>stop_reason</span> is inspected. Every Claude 5 refusal in this suite came from bare code prompts over the raw API; the Maia agent evals run on Fable without a single refusal.</li>
</ul>
<h2>Recommendation</h2>
<p>For autonomous code agents on the raw API, Gemini 3.8 Flash, Kimi K3 and Grok 4.5 are the frictionless choices, with Gemini now leading on accuracy and cost. Fable 5.1 is viable where a supervising loop can detect a refusal and re-route (its accuracy is the best in the set), and its refusal rate should be re-measured on each model release since it moved from 30 to 8 between Fable 5 and 5.1. Keep the suite in the repository and re-run <span class=mono>calibrate</span> before every comparison.</p>
<h2>Appendix — non-refusal failures per model</h2>
<table><tr><th>model</th><th>category</th><th>problem</th><th>first failing case</th></tr>%s</table>
<div class=foot>Sources: Braintrust project "code-benchmarks", experiments code-bench-v4__* (7 models × 48 rows, per-test detail in metadata); repository code-benchmarks (harness, tests, outputs, this report). Prepared by Andrés Espitia with Claude Code.</div>
</body></html>""" % (css, date.today().isoformat(), gg["cost"] or 0, g51["n_empty"], rows_html, mhead, matrix, july_rows,
                     g51["tok"], g51["lat"], gg["cost"] or 0, gg["lat"], gg["tok"], fail_rows)
    open(out, "w").write(body)
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1])
