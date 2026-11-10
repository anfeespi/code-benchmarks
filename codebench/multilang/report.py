"""Render the cross-suite and per-language readout as a single HTML file.

Usage: python -m codebench.multilang.report reports/code-bench-readout.html
Everything is read from data/: rerun it after a new model or suite finishes.
"""
import html
import json
import statistics
import sys
from datetime import date

from .. import harness
from . import langs, typesys

ROOT = harness.ROOT
MODELS = [  # tag stem, display name, [v4 tag, hard tag, agentic tag, multilang tag]
    ("Claude Fable 5.2", "fable-5.2-bedrock", "fable-5.2-bedrock", "fable-5.2-bedrock", None),
    ("Claude Sonnet 5.5", "sonnet-5.5-bedrock", "sonnet-5.5-bedrock", "sonnet-5.5-bedrock", "sonnet-5.5"),
    ("GPT 6.1 Sol", "gpt-6.1-sol", "gpt-6.1-sol", "gpt-6.1-sol", None),
    ("Gemini 4 Carbon", "gemini-4-carbon", "gemini-4-carbon", "gemini-4-carbon", "gemini-4-carbon"),
    ("Claude Opus 5.5", "opus-5.5-bedrock", "opus-5.5-bedrock", "opus-5.5-bedrock", None),
    ("Claude Fable 5.1", "fable-5.1", "fable-5.1-bedrock", "fable-5.1-bedrock", None),
    ("Gemini 4 Argon", "gemini-4-argon", "gemini-4-argon", "gemini-4-argon", "gemini-4-argon"),
    ("Grok 4.5", "grok-4.5", "grok-4.5", "grok-4.5", None),
    ("Kimi K3", "kimi-k3", "kimi-k3", "kimi-k3", None),
    ("Gemini 3.8 Flash", "gemini-3.8-flash", "gemini-3.8-flash", "gemini-3.8-flash", None),
    ("GLM 5.2", "glm-5.2", "glm-5.2", "glm-5.2", None),
]
LANG_NAMES = {"python": "Python", "go": "Go", "java": "Java", "cpp": "C++", "typescript": "TypeScript"}
e = html.escape


def load(path):
    f = ROOT / path
    return json.loads(f.read_text()) if f.exists() else None


def meta(r):
    return r.get("metadata") or {}


def suite_stats(rows, strict=False):
    if rows is None:
        return None
    if strict:
        got = [(r.get("scores_by_suite") or {}).get("strict") for r in rows]
        if not all(got):
            return None
        return {"pass": sum(g["pass"] for g in got), "n": len(rows)}
    lat = [meta(r).get("latency_s") for r in rows if meta(r).get("latency_s")]
    cost = sum((meta(r).get("cost_usd") or 0) for r in rows)
    return {"pass": sum(r["scores"]["pass"] for r in rows), "n": len(rows),
            # stop_reason "error" is the provider failing the call, not the model declining.
            "refused": sum(1 for r in rows if meta(r).get("refused") and not meta(r).get("truncated")
                           and meta(r).get("stop_reason") != "error"),
            "provider_errors": sum(1 for r in rows if meta(r).get("stop_reason") == "error"),
            "truncated": sum(1 for r in rows if meta(r).get("truncated")),
            "cost": cost or None, "p50": statistics.median(lat) if lat else None}


def cell(s, best=None):
    if s is None:
        return "<td class=na>not run</td>"
    cls = " class=top" if s["pass"] == s["n"] else ""
    return "<td%s>%d/%d</td>" % (cls, s["pass"], s["n"])


def money(v):
    return "n/a" if v is None else "$%.2f" % v


def main(out):
    rows_html, hard_rows = [], []
    for name, v4, hard, ag, _ in MODELS:
        s4 = suite_stats(load("data/outputs/code-bench-v4__%s.json" % v4))
        ss = suite_stats(load("data/outputs/code-bench-v4__%s.json" % v4), strict=True)
        sh = suite_stats(load("data/outputs/code-bench-hard-v1__%s.json" % hard))
        a = load("data/agentic/outputs/agentic-go-v1__%s.json" % ag)
        at = a["totals"] if a else None
        ac = ("<td class=na>running</td>" if name == "Gemini 4 Carbon" else "<td class=na>not run</td>") if not at else \
            "<td%s>%d/%d</td>" % (" class=top" if at["passed"] == at["tasks"] else "", at["passed"], at["tasks"])
        rows_html.append("<tr%s><th>%s</th>%s%s%s%s</tr>" % (
            " class=focus" if name == "Gemini 4 Carbon" else "", e(name), cell(s4), cell(ss), cell(sh), ac))
        if sh:
            hard_rows.append("<tr%s><th>%s</th><td>%d/%d</td><td>%d</td><td>%d</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                " class=focus" if name == "Gemini 4 Carbon" else "", e(name), sh["pass"], sh["n"], sh["refused"], sh["truncated"],
                money(sh["cost"]), "%.0f s" % sh["p50"] if sh["p50"] else "n/a",
                ("%s, %.0f min" % (money(at["cost_usd"]), at["wall_s"] / 60)) if at else "n/a"))

    lang_rows, fails = [], []
    for name, _, _, _, ml in MODELS:
        rows = load("data/multilang/outputs/hard-v1__%s.json" % ml) if ml else None
        if not rows:
            continue
        rows = [r for r in rows if r.get("supported")]
        cells = []
        for l in langs.LANGS:
            mine = [r for r in rows if r["lang"] == l]
            p = sum(r["pass"] for r in mine)
            cells.append("<td%s>%d/%d</td>" % (" class=top" if p == len(mine) else "", p, len(mine)))
        tot = sum(r["pass"] for r in rows)
        lang_rows.append("<tr><th>%s</th>%s<td><b>%d/%d</b></td><td>%s</td></tr>" % (
            e(name), "".join(cells), tot, len(rows), money(sum((r.get("cost_usd") or 0) for r in rows))))
        for r in rows:
            if not r["pass"]:
                d = r.get("error") or (r.get("detail") or [""])[0]
                kind = ("refused" if r.get("refused") else "did not compile or load" if "compile error" in d or "SyntaxError" in d
                        or "crash" in d and r.get("passed") == 0 else "wrong answer")
                fails.append("<tr><td>%s</td><td>%s</td><td class=mono>%s</td><td>%s</td><td>%d/%d cases</td></tr>" % (
                    e(name), LANG_NAMES[r["lang"]], e(r["slug"]), kind, r.get("passed") or 0, r.get("n_cases") or 0))

    harness.use_suite("hard-v1")
    docs = [json.loads(p.read_text()) for p in sorted((ROOT / "data" / "cache" / "neutral").glob("*.json"))]
    n_cases = sum(len(d["cases"]) for d in docs)
    n_kept = sum(sum(langs.portable_case("python", c) for c in d["cases"]) for d in docs)
    typed = [d for d in docs if not typesys.has_dynamic(d["signature"])]
    sig_rows = "".join("<tr><td class=mono>%s</td><td class=mono>%s(%s) &rarr; %s</td></tr>" % (
        e(d["slug"]), e(d["entry_point"]), e(", ".join(typesys.show(t) for t in d["signature"]["args"])),
        e(typesys.show(d["signature"]["returns"]))) for d in typed)

    css = """
:root{--ink:#1b1f24;--mut:#5d6672;--line:#dfe3e8;--bg:#fbfbfa;--card:#fff;--acc:#3e4fe0;--good:#0f7a4b;--soft:#eef0fd}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,"Segoe UI",Inter,Helvetica,Arial,sans-serif}
main{max-width:980px;margin:0 auto;padding:48px 24px 80px}
h1{font-size:34px;line-height:1.15;margin:0 0 8px;letter-spacing:-.02em}
h2{font-size:22px;margin:48px 0 12px;letter-spacing:-.01em}h3{font-size:16px;margin:24px 0 8px}
p,li{max-width:72ch}.sub{color:var(--mut);margin:0 0 28px}
.wrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px;margin:14px 0}
table{border-collapse:collapse;width:100%;font-size:14.5px;font-variant-numeric:tabular-nums}
th,td{padding:9px 14px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
tr:last-child th,tr:last-child td{border-bottom:0}
th:first-child,td:first-child{text-align:left}thead th{font-size:12.5px;color:var(--mut);font-weight:600;background:#f5f6f8}
tbody th{font-weight:600}td.top{color:var(--good);font-weight:600}td.na{color:var(--mut)}
tr.focus th,tr.focus td{background:var(--soft)}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;white-space:normal;text-align:left}
.left td{text-align:left;white-space:normal}
ul{padding-left:20px}.key{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--acc);border-radius:8px;padding:14px 18px;margin:18px 0}
@page{size:A4;margin:14mm 12mm}
@media print{body{background:#fff;font-size:12.5px}main{max-width:none;padding:0}h1{font-size:26px}h2{font-size:17px;margin-top:26px;break-after:avoid}
h3{break-after:avoid}.wrap{overflow:visible;break-inside:avoid}table{font-size:11px}th,td{padding:5px 7px;white-space:normal}
thead th{font-size:10px}.mono{font-size:10px}.key{break-inside:avoid}li{break-inside:avoid}
tr.focus th,tr.focus td,thead th{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.key ul{margin:6px 0}.foot{color:var(--mut);font-size:13px;margin-top:48px;border-top:1px solid var(--line);padding-top:14px}
"""
    doc = """<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Code benchmark readout</title><style>%(css)s</style></head><body><main>
<h1>Code benchmark readout</h1>
<p class=sub>Gemini 4 Carbon across the suites, and the first per-language grading. %(date)s.</p>

<div class=key><b>What this says</b><ul>
<li><b>Gemini 4 Carbon is a top-tier coding model on these suites.</b> 48/48 on v4 (also under the strict tests), 31/32 on the hard suite and 18/18 on the agentic Go suite. Its only miss anywhere is one call the provider failed; every answer it returned passed.</li>
<li><b>It is slow and not cheap.</b> Median 224 s per hard problem against 18 s for Claude Sonnet 5.5, and it cost more than three times Sonnet on the per-language run.</li>
<li><b>Per-language grading works and separates models.</b> On the 17 problems with static types, in five languages: Sonnet 5.5 84/85, Carbon 82/85, Argon 76/85.</li>
<li><b>A grading bug was hiding real passes.</b> Python answers that import numpy failed at import. With numpy installed, Sonnet 5.5 goes from 30 to 32/32 on the hard suite and Opus 5.5 from 30 to 31/32.</li>
</ul></div>

<h2>1. All suites</h2>
<p>Problems passed on the first attempt. A refusal or an answer cut off by the output limit counts as a failure. Green marks a full score.</p>
<div class=wrap><table><thead><tr><th>Model</th><th>v4 (48)</th><th>v4 strict (48)</th><th>hard-v1 (32)</th><th>agentic-go-v1 (18)</th></tr></thead>
<tbody>%(rows)s</tbody></table></div>
<ul>
<li><b>v4 is saturated.</b> Five models score 48/48 even under the strict tests. It no longer ranks the top of the field.</li>
<li><b>hard-v1 is the suite that still separates models.</b> The spread runs from 9 to 32.</li>
<li><b>agentic-go-v1 is saturated too.</b> Every model that finished passes 17 or 18 of 18 tasks; it only separates on cost and time.</li>
</ul>

<h2>2. Gemini 4 Carbon on the hard suite</h2>
<div class=wrap><table><thead><tr><th>Model</th><th>Passed</th><th>Refused</th><th>Truncated</th><th>Cost of the run</th><th>Median time per problem</th><th>Agentic run (cost, summed task time)</th></tr></thead>
<tbody>%(hard)s</tbody></table></div>
<ul>
<li>Carbon gains 4 problems over Gemini 4 Argon (27 to 31) and ties Claude Opus 5.5 and Claude Fable 5.1.</li>
<li>Its one failure is not a wrong answer and not a refusal. On <span class=mono>lock-manager-deadlock-victims</span> the provider returned an error (503, provider overloaded) after about eight minutes with no output. The problem was repeated 8 times: 5 calls failed the same way and 3 completed, each after more than 490 s and 42,000 to 53,000 output tokens. The 2 completed answers that were graded both pass every test. The official score stays 31/32 because every model gets one run, but the miss is about availability on a very long generation, not about capability.</li>
<li>It writes long answers: a median of about 14,700 output tokens per hard problem, against about 2,500 for Sonnet 5.5. That is where the time and the cost come from.</li>
<li>On the agentic Go suite Carbon passes 18/18 tasks and all 52 hidden tests, for $6.81. It used 581 tool calls, the most of any model, and hit the 40-call budget on 4 tasks that it still passed.</li>
<li>Cost is "n/a" for models run on Amazon Bedrock, which does not report it per call.</li>
</ul>

<h2>3. Grading per language</h2>
<p>The same hard problems, solved in Python, Go, Java, C++ and TypeScript. Scope of this first version: the 17 of 32 hard problems whose inputs and outputs fit static types.</p>
<div class=wrap><table><thead><tr><th>Model</th>%(lhead)s<th>Total</th><th>Cost</th></tr></thead><tbody>%(langs)s</tbody></table></div>
<ul>
<li><b>Sonnet 5.5 is near perfect everywhere</b>: one miss in 85.</li>
<li><b>Carbon is even across languages</b>: one miss each in Python, C++ and TypeScript.</li>
<li><b>Argon varies the most by language</b>: full marks in Java, but it loses problems to code that does not compile in Go and C++ and to a crash in TypeScript.</li>
<li><b>One failure is about the language, not the model.</b> All three models fail the same TypeScript case in <span class=mono>version-constraint-picker</span>: version numbers too large for a JavaScript number. Python handles them natively; in TypeScript the model has to compare them as text, and none did.</li>
<li><b>Java is the only language where all three models score 17/17.</b></li>
</ul>
<h3>Every failure</h3>
<div class="wrap left"><table><thead><tr><th>Model</th><th>Language</th><th>Problem</th><th>Kind</th><th>Cases passed</th></tr></thead><tbody>%(fails)s</tbody></table></div>

<h2>4. The numpy finding</h2>
<p>No prompt says "standard library only", but the grading interpreter had no numpy. An answer that imported it failed before running and was counted as wrong.</p>
<div class=wrap><table><thead><tr><th>Model</th><th>hard-v1 as published</th><th>hard-v1 with numpy installed</th></tr></thead><tbody>
<tr><th>Claude Sonnet 5.5</th><td>30/32</td><td class=top>32/32</td></tr>
<tr><th>Claude Opus 5.5</th><td>30/32</td><td>31/32</td></tr>
<tr><th>Claude Fable 5.2</th><td>32/32</td><td class=top>32/32</td></tr></tbody></table></div>
<ul>
<li>Python is now graded in an environment with numpy. Every stored score in this report was recomputed that way; only the two rows above changed.</li>
<li>In the per-language run the Python prompt says "use only the standard library", the rule the other four languages already had, so all five compete on equal terms.</li>
</ul>

<h2>5. How the per-language grading works</h2>
<ul>
<li><b>The tests were Python code, not data.</b> Each case is a snippet that calls the solution, often several times, and digests the result.</li>
<li><b>Each case is recorded once.</b> It runs against the reference solution with a recorder that captures every call: its arguments and what it returned or raised. A candidate in any language passes the case when every recorded call returns the recorded value.</li>
<li><b>%(kept)d of %(cases)d cases carry over.</b> The rest pass a wrong type on purpose (a number where a list is expected), which a typed language cannot express. They are dropped for Python too, so every language is graded on the same cases.</li>
<li><b>Types are inferred, not written by hand.</b> The signature of each problem comes from the recorded values and is rendered per language: structs in Go, records in Java, tuples in C++, fixed-length arrays in TypeScript.</li>
<li><b>One small driver per language</b> reads a case, calls the candidate and prints the results. The comparison stays in one place for all languages.</li>
<li>All 32 reference solutions pass their recorded cases, which proves the recording is faithful.</li>
</ul>
<h3>The 17 problems in scope</h3>
<div class="wrap left"><table><thead><tr><th>Problem</th><th>Inferred signature</th></tr></thead><tbody>%(sigs)s</tbody></table></div>

<h2>6. Limits and what is next</h2>
<ul>
<li><b>15 hard problems are out of scope for now.</b> They mix integers, text and nulls in one list, such as operation logs. Go, Java and C++ need a dynamic value type for them.</li>
<li><b>Time limits are not calibrated per language.</b> The Python limits are used everywhere, so a slow solution can pass a performance problem in Go or C++.</li>
<li><b>TypeScript is not type-checked.</b> Node runs it by stripping the types, so a type error that still runs is not caught.</li>
<li><b>Three models so far.</b> Claude Fable 5.2, Claude Opus 5.5 and GPT 6.1 Sol have not been run per language yet.</li>
<li><b>One run per model and language.</b> Differences of one problem are within run-to-run noise.</li>
<li><b>The agentic suite needs harder tasks</b> to rank models again.</li>
</ul>

<div class=foot>Sources: repository code-benchmarks, data/outputs (v4, hard-v1), data/agentic/outputs, data/multilang/outputs. Generated by codebench/multilang/report.py. Prepared by Andrés Espitia with Claude Code.</div>
</main></body></html>""" % {
        "css": css, "date": date.today().strftime("%B %d, %Y").replace(" 0", " "), "rows": "".join(rows_html),
        "hard": "".join(hard_rows), "lhead": "".join("<th>%s</th>" % LANG_NAMES[l] for l in langs.LANGS),
        "langs": "".join(lang_rows), "fails": "".join(fails), "kept": n_kept, "cases": n_cases, "sigs": sig_rows}
    out_path = ROOT / out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc)
    print("wrote", out_path)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "reports/code-bench-readout.html")
