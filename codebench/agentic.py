"""agentic-go-v1: agentic Go engineering track.

A model gets a Jira-style ticket and a temp copy of a small payments microservice
(agentic/go-payments with the task's start.patch applied) and works in a tool loop:
list_files, read_file, write_file, apply_edit, run (go build/test/vet, gofmt only) and
finish. Grading copies the task's HIDDEN acceptance tests in (the model never sees
them) and runs `go test -race -count=1 ./...`.

Commands
  verify   reference solutions pass every hidden test, start states fail them
  run      run a model on the track
  grade    grade an arbitrary directory against a task (debugging)

  uv run --python 3.12 python -m codebench.agentic verify
  uv run --python 3.12 python -m codebench.agentic run --provider openrouter \
      --model google/gemini-3.8-flash --tag gemini-3.8-flash --key-file /tmp/openrouter-key.txt
  uv run --python 3.12 --with boto3 python -m codebench.agentic run --provider bedrock \
      --model global.anthropic.claude-sonnet-5-5 --aws-profile agentland-dev --region us-east-1 \
      --tag sonnet-5.5-bedrock

Budget per task: --max-calls tool calls (default 40) and --max-context-tokens (default
150k): the run stops when a single request's prompt exceeds it. --max-cost-usd caps the
whole run (default 25). Output: transcripts data/agentic/runs/<tag>/<task>.jsonl and the
summary data/agentic/outputs/agentic-go-v1__<tag>.json. Tasks whose transcript already
ends with a result are reused unless listed in --only.
"""
import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUITE = "agentic-go-v1"
BASE = ROOT / "agentic" / "go-payments"
TASKS = ROOT / "agentic" / "tasks"
RUNS = ROOT / "data" / "agentic" / "runs"
OUTPUTS = ROOT / "data" / "agentic" / "outputs"
MODULE = "example.com/gopayments"
MAX_TOKENS = int(os.environ.get("AGENTIC_MAX_TOKENS", "16000"))
TOOL_OUTPUT_LIMIT = 12000
RUN_TIMEOUT_S = 180
GRADE_TIMEOUT_S = 600

# USD per million tokens: input, output, cache read, cache write. Anthropic list prices;
# Bedrock bills Claude at partner prices that may differ. OpenRouter returns the real
# cost in its usage block, so it needs no table.
PRICES = {
    "claude-fable-5-1": (10.0, 50.0, 0.25, 12.5),
    "claude-opus-5-5": (4.0, 20.0, 0.20, 5.0),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20, 2.5),
}

GO_ENV = dict(os.environ, GOTOOLCHAIN="local", GOPROXY="off", GOFLAGS="-mod=mod", GOWORK="off")


# --------------------------------------------------------------------------- tasks

def load_tasks():
    out = []
    for d in sorted(p for p in TASKS.iterdir() if p.is_dir() and (p / "task.json").exists()):
        t = json.loads((d / "task.json").read_text())
        t["dir"] = d
        out.append(t)
    return out


def _patch(dest: Path, patch: Path):
    if not patch.exists() or not patch.read_text().strip():
        return
    r = subprocess.run(["patch", "-p1", "-s", "--forward", "-i", str(patch)], cwd=dest, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("patch %s failed: %s%s" % (patch, r.stdout, r.stderr))


def materialize(task, dest: Path, stage="start"):
    """Copy the base module to dest and apply the task's start (and solution) patch."""
    shutil.copytree(BASE, dest)
    _patch(dest, task["dir"] / "start.patch")
    if stage == "solution":
        _patch(dest, task["dir"] / "solution.patch")


def hidden_files(task):
    h = task["dir"] / "hidden"
    return sorted(p for p in h.rglob("*_test.go"))


def hidden_test_ids(task):
    ids = []
    for f in hidden_files(task):
        rel = f.relative_to(task["dir"] / "hidden").parent.as_posix()
        pkg = MODULE if rel == "." else MODULE + "/" + rel
        for name in re.findall(r"^func (Test\w+)\(\w+ \*testing\.T\)", f.read_text(), re.M):
            ids.append(pkg + "." + name)
    return ids


# --------------------------------------------------------------------------- go runner

def go(cmd, cwd, timeout):
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=GO_ENV)
        return r.returncode, r.stdout + r.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        return -1, out + "\n[timed out after %ds]" % timeout, time.time() - t0


def test_results(cwd, race=True):
    """Run the whole suite with -json; returns ({pkg.Test: pass|fail|skip}, raw_tail)."""
    cmd = ["go", "test", "-count=1", "-json", "-timeout", "300s"] + (["-race"] if race else []) + ["./..."]
    _, out, _ = go(cmd, cwd, GRADE_TIMEOUT_S)
    res, text, build = {}, [], []
    for line in out.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            build.append(line)
            continue
        test = ev.get("Test")
        if ev.get("Action") == "output" and ev.get("Output"):
            text.append(ev["Output"].rstrip("\n"))
        if not test or "/" in test or ev.get("Action") not in ("pass", "fail", "skip"):
            continue
        res[ev["Package"] + "." + test] = ev["Action"]
    return res, "\n".join(build[:60] + text[-80:])


def grade(task, workdir: Path, baseline=None):
    """Grade a working tree: vet/gofmt on the model's code, then hidden + visible tests."""
    _, fmt_out, _ = go(["gofmt", "-l", "."], workdir, 60)
    vet_rc, vet_out, _ = go(["go", "vet", "./..."], workdir, 180)
    build_rc, build_out, _ = go(["go", "build", "./..."], workdir, 180)
    for f in hidden_files(task):
        dst = workdir / f.relative_to(task["dir"] / "hidden")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dst)
    res, tail = test_results(workdir)
    hidden = hidden_test_ids(task)
    hidden_res = {h: res.get(h, "missing") for h in hidden}
    visible = {k: v for k, v in res.items() if k not in hidden_res}
    broke = []
    if baseline is not None:
        broke = sorted(k for k, v in baseline.items() if v == "pass" and visible.get(k) != "pass")
    return {
        "pass": all(v == "pass" for v in hidden_res.values()),
        "hidden_passed": sum(v == "pass" for v in hidden_res.values()),
        "hidden_total": len(hidden_res),
        "hidden": hidden_res,
        "visible_failed": sorted(k for k, v in visible.items() if v == "fail"),
        "broke_visible": broke,
        "build_ok": build_rc == 0,
        "vet_clean": vet_rc == 0,
        "gofmt_clean": fmt_out.strip() == "",
        "gofmt_files": fmt_out.split(),
        "diagnostics": (build_out[-2000:] if build_rc else "") + ("" if vet_rc == 0 else vet_out[-2000:]),
        "test_tail": tail[-6000:],
    }


def baseline_visible(task):
    with tempfile.TemporaryDirectory(prefix="agentic-base-") as tmp:
        d = Path(tmp) / "repo"
        materialize(task, d)
        res, _ = test_results(d)
    return res


# --------------------------------------------------------------------------- tools

TOOLS = [
    {"name": "list_files", "description": "List files of the repository (recursive), relative to the repo root.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Directory relative to the repo root; default '.'"}},
                    "required": []}},
    {"name": "read_file", "description": "Read a text file. Returns numbered lines starting at `offset` (1-based).",
     "parameters": {"type": "object", "properties": {
         "path": {"type": "string"}, "offset": {"type": "integer", "description": "First line, 1-based (default 1)"},
         "limit": {"type": "integer", "description": "Max lines (default 400, max 1000)"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Create or overwrite a file with the given full content.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                    "required": ["path", "content"]}},
    {"name": "apply_edit", "description": "Replace exactly one occurrence of `old` with `new` in a file. `old` must match the file exactly (including whitespace) and be unique.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}},
                    "required": ["path", "old", "new"]}},
    {"name": "run", "description": "Run a command in the repo root. Allowed: `go build ./...`, `go vet ./...`, `gofmt -l .`, and `go test` with optional flags -race, -count=N, -v, -run REGEX and package patterns (./... or ./pkg). Timeout %ds." % RUN_TIMEOUT_S,
     "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "finish", "description": "Call when the ticket is resolved. Ends the session.",
     "parameters": {"type": "object", "properties": {"summary": {"type": "string", "description": "What you changed and why"}},
                    "required": ["summary"]}},
]

SYSTEM = """You are a senior Go engineer on the payments team. Your working directory is the go-payments service, a Go module (stdlib only). Resolve the Jira ticket in the user message by changing the code.

Tools: list_files, read_file, write_file, apply_edit, run, finish. There is no shell, network or git; `run` only accepts go build/vet/test and gofmt as described in its schema.

Your work is graded automatically with hidden acceptance tests (`go test -race`), the existing test suite, `go vet` and gofmt. Follow the conventions of the codebase, keep public APIs and constructors stable unless the ticket requires a change, and do not weaken existing tests. You have a budget of {max_calls} tool calls. Call finish with a short summary when you are done."""


class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, p):
        if not p or os.path.isabs(p):
            raise ValueError("path must be relative to the repo root")
        full = (self.root / p).resolve()
        if full != self.root and self.root not in full.parents:
            raise ValueError("path escapes the repository")
        return full

    def list_files(self, path="."):
        d = self._path(path or ".")
        if not d.is_dir():
            raise ValueError("not a directory: %s" % path)
        files = sorted(f.relative_to(self.root).as_posix() for f in d.rglob("*") if f.is_file())
        return "\n".join(files) or "(empty)"

    def read_file(self, path, offset=1, limit=400):
        f = self._path(path)
        if not f.is_file():
            raise ValueError("no such file: %s" % path)
        lines = f.read_text(errors="replace").splitlines()
        offset = max(1, int(offset or 1))
        limit = max(1, min(int(limit or 400), 1000))
        chunk = lines[offset - 1: offset - 1 + limit]
        body = "\n".join("%5d\t%s" % (i, l) for i, l in enumerate(chunk, offset))
        more = len(lines) - (offset - 1 + len(chunk))
        return body + ("\n[... %d more lines]" % more if more > 0 else "") if chunk else "(no lines in range; file has %d lines)" % len(lines)

    def write_file(self, path, content):
        f = self._path(path)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)
        return "wrote %s (%d bytes)" % (path, len(content.encode()))

    def apply_edit(self, path, old, new):
        f = self._path(path)
        if not f.is_file():
            raise ValueError("no such file: %s" % path)
        text = f.read_text()
        n = text.count(old) if old else 0
        if n != 1:
            raise ValueError("`old` found %d times in %s; it must match exactly once" % (n, path))
        f.write_text(text.replace(old, new, 1))
        return "edited %s" % path

    def run(self, command):
        argv = parse_command(command)
        rc, out, dt = go(argv, self.root, RUN_TIMEOUT_S)
        return "$ %s\n%s\n[exit %d, %.1fs]" % (" ".join(argv), out.strip() or "(no output)", rc, dt)


_PKG = re.compile(r"^\./[A-Za-z0-9_./-]*$")


def parse_command(command):
    argv = shlex.split(command or "")
    if argv in (["go", "build", "./..."], ["go", "vet", "./..."], ["gofmt", "-l", "."]):
        return argv
    if argv[:2] == ["go", "vet"] and len(argv) > 2 and all(_PKG.match(a) and ".." not in a.replace("...", "") for a in argv[2:]):
        return argv
    if argv[:2] == ["go", "test"] and len(argv) > 2:
        out, i, pkgs = ["go", "test"], 2, 0
        while i < len(argv):
            a = argv[i]
            if a in ("-race", "-v") or re.fullmatch(r"-count=\d+", a):
                out.append(a)
            elif a == "-run" and i + 1 < len(argv):
                out += [a, argv[i + 1]]
                i += 1
            elif a.startswith("-run="):
                out.append(a)
            elif _PKG.match(a) and ".." not in a.replace("...", ""):
                out.append(a)
                pkgs += 1
            else:
                raise ValueError("argument not allowed: %r" % a)
            i += 1
        if pkgs:
            return out
    raise ValueError("command not allowed: %r. Allowed: go build ./..., go vet ./..., gofmt -l ., go test [-race] [-count=N] [-v] [-run REGEX] <./pkg|./...>" % command)


def execute(ws: Workspace, name, args):
    """Run one tool call; returns (text, is_error)."""
    try:
        if not isinstance(args, dict):
            raise ValueError("arguments must be a JSON object")
        if name == "list_files":
            out = ws.list_files(args.get("path", "."))
        elif name == "read_file":
            out = ws.read_file(args["path"], args.get("offset", 1), args.get("limit", 400))
        elif name == "write_file":
            out = ws.write_file(args["path"], args["content"])
        elif name == "apply_edit":
            out = ws.apply_edit(args["path"], args["old"], args["new"])
        elif name == "run":
            out = ws.run(args["command"])
        elif name == "finish":
            out = "session finished"
        else:
            raise ValueError("unknown tool %r" % name)
        err = False
    except KeyError as e:
        out, err = "missing argument %s" % e, True
    except Exception as e:  # noqa: BLE001 - every tool failure goes back to the model
        out, err = "error: %s" % e, True
    if len(out) > TOOL_OUTPUT_LIMIT:
        out = out[:TOOL_OUTPUT_LIMIT // 2] + "\n[... %d chars truncated ...]\n" % (len(out) - TOOL_OUTPUT_LIMIT) + out[-TOOL_OUTPUT_LIMIT // 2:]
    return out, err


# --------------------------------------------------------------------------- providers

class OpenRouter:
    """OpenAI-compatible chat completions with tool calling. The assistant message is
    appended exactly as returned (incl. reasoning_details, which some providers need
    echoed back across tool calls)."""

    def __init__(self, model, key):
        self.model, self.key = model, key

    def start(self, system, user):
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def step(self, messages):
        body = {"model": self.model, "messages": messages, "temperature": 0, "max_tokens": MAX_TOKENS,
                "tools": [{"type": "function", "function": t} for t in TOOLS], "tool_choice": "auto",
                "usage": {"include": True}}
        last = None
        for attempt in range(4):
            req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                         headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json",
                                                  "HTTP-Referer": "https://y.uno", "X-Title": "code-bench-agentic"})
            try:
                with urllib.request.urlopen(req, timeout=600) as r:
                    resp = json.load(r)
                if "choices" in resp and resp["choices"]:
                    break
                last = "bad response: %s" % json.dumps(resp)[:300]
            except urllib.error.HTTPError as e:
                last = "%s %s" % (e.code, e.read()[:300].decode(errors="replace"))
            except Exception as e:  # noqa: BLE001
                last = "%s: %s" % (type(e).__name__, e)
            time.sleep(4 * (attempt + 1))
        else:
            raise RuntimeError(last)
        ch = resp["choices"][0]
        msg = ch.get("message", {})
        msg = {k: v for k, v in msg.items() if v is not None and k != "refusal"}
        msg["role"] = "assistant"
        calls = []
        for tc in msg.get("tool_calls") or []:
            raw = tc.get("function", {}).get("arguments") or "{}"
            try:
                args = json.loads(raw)
            except ValueError:
                args = {"__invalid_json__": raw}
            calls.append((tc.get("id"), tc.get("function", {}).get("name"), args))
        u = resp.get("usage", {})
        cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        usage = {"in": u.get("prompt_tokens") or 0, "out": u.get("completion_tokens") or 0, "cache_read": cached,
                 "cache_write": 0, "cost": u.get("cost") or 0.0, "prompt": u.get("prompt_tokens") or 0}
        return {"assistant": msg, "text": msg.get("content") or "", "calls": calls, "usage": usage,
                "stop": ch.get("finish_reason")}

    def results(self, messages, results):
        for call_id, text, _err in results:
            messages.append({"role": "tool", "tool_call_id": call_id, "content": text})

    def nudge(self, messages, text):
        messages.append({"role": "user", "content": text})


class Bedrock:
    """Bedrock converse with toolConfig. Assistant turns are appended verbatim
    (reasoningContent blocks included, as adaptive-thinking models require), so the
    history is append-only. Cache points: tools, system and, per request only, the last
    message."""

    def __init__(self, model, session):
        self.model = model
        self.client = session.client("bedrock-runtime")
        self.price = next((v for k, v in PRICES.items() if k in model), None)
        if self.price is None:
            raise SystemExit("no price for %s in PRICES" % model)

    def start(self, system, user):
        self.system = [{"text": system}, {"cachePoint": {"type": "default"}}]
        tools = [{"toolSpec": {"name": t["name"], "description": t["description"], "inputSchema": {"json": t["parameters"]}}}
                 for t in TOOLS]
        self.tool_config = {"tools": tools + [{"cachePoint": {"type": "default"}}]}
        return [{"role": "user", "content": [{"text": user}]}]

    def step(self, messages):
        msgs = messages[:-1] + [dict(messages[-1], content=messages[-1]["content"] + [{"cachePoint": {"type": "default"}}])]
        last = None
        for attempt in range(6):
            try:
                resp = self.client.converse(modelId=self.model, messages=msgs, system=self.system,
                                            toolConfig=self.tool_config, inferenceConfig={"maxTokens": MAX_TOKENS})
                break
            except Exception as e:  # noqa: BLE001
                last = "%s: %s" % (type(e).__name__, str(e)[:400])
                if not any(s in last for s in ("Throttling", "ServiceUnavailable", "InternalServer", "ModelError", "timeout", "Timeout")):
                    raise RuntimeError(last)
                time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(last)
        msg = resp["output"]["message"]
        content = msg.get("content", [])
        calls = [(b["toolUse"]["toolUseId"], b["toolUse"]["name"], b["toolUse"].get("input") or {}) for b in content if "toolUse" in b]
        text = "".join(b.get("text", "") for b in content if "text" in b)
        u = resp.get("usage", {})
        tin, tout = u.get("inputTokens", 0), u.get("outputTokens", 0)
        cr, cw = u.get("cacheReadInputTokens", 0) or 0, u.get("cacheWriteInputTokens", 0) or 0
        p_in, p_out, p_cr, p_cw = self.price
        cost = (tin * p_in + tout * p_out + cr * p_cr + cw * p_cw) / 1e6
        usage = {"in": tin + cr + cw, "out": tout, "cache_read": cr, "cache_write": cw, "cost": cost, "prompt": tin + cr + cw}
        return {"assistant": {"role": "assistant", "content": content}, "text": text, "calls": calls, "usage": usage,
                "stop": resp.get("stopReason")}

    def results(self, messages, results):
        blocks = [{"toolResult": {"toolUseId": cid, "content": [{"text": text}], "status": "error" if err else "success"}}
                  for cid, text, err in results]
        messages.append({"role": "user", "content": blocks})

    def nudge(self, messages, text):
        messages.append({"role": "user", "content": [{"text": text}]})


# --------------------------------------------------------------------------- loop

class Spend:
    def __init__(self, cap):
        self.cap, self.total, self.lock = cap, 0.0, threading.Lock()

    def add(self, x):
        with self.lock:
            self.total += x or 0.0
            return self.total

    def exceeded(self):
        with self.lock:
            return self.total >= self.cap


def run_task(task, provider, a, spend: Spend, log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = open(log_path, "w")

    def emit(**ev):
        ev["t"] = round(time.time(), 3)
        log.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
        log.flush()

    t0 = time.time()
    tmp = Path(tempfile.mkdtemp(prefix="agentic-%s-" % task["id"][:2]))
    repo = tmp / "go-payments"
    materialize(task, repo)
    ws = Workspace(repo)
    system = SYSTEM.format(max_calls=a.max_calls)
    messages = provider.start(system, task["ticket"])
    emit(event="start", task=task["id"], model=a.model, provider=a.provider, system=system, ticket=task["ticket"],
         budget={"max_calls": a.max_calls, "max_context_tokens": a.max_context_tokens})
    calls = turns = nudges = 0
    tok = {"in": 0, "out": 0, "cache_read": 0, "cache_write": 0}
    cost, stop, summary, error = 0.0, None, None, None
    try:
        while stop is None:
            if spend.exceeded():
                stop = "run_cost_cap"
                break
            turns += 1
            r = provider.step(messages)
            u = r["usage"]
            for k in tok:
                tok[k] += u.get(k, 0) or 0
            cost += u.get("cost") or 0.0
            spend.add(u.get("cost"))
            messages.append(r["assistant"])
            emit(event="assistant", turn=turns, text=r["text"], calls=[{"id": c[0], "name": c[1], "args": c[2]} for c in r["calls"]],
                 stop=r["stop"], usage=u, message=r["assistant"])
            if not r["calls"]:
                if nudges < 1 and r["stop"] not in ("refusal", "content_filtered"):
                    nudges += 1
                    provider.nudge(messages, "Continue working with the tools. Call finish when the ticket is resolved.")
                    continue
                stop = "no_tool_call"
                break
            results = []
            for cid, name, args in r["calls"]:
                if calls >= a.max_calls:
                    results.append((cid, "error: tool-call budget exhausted", True))
                    stop = stop or "budget_tool_calls"
                    continue
                calls += 1
                out, err = execute(ws, name, args)
                results.append((cid, out, err))
                emit(event="tool", turn=turns, n=calls, name=name, args=args, error=err, result=out)
                if name == "finish" and not err:
                    stop, summary = "finished", args.get("summary")
            provider.results(messages, results)
            if stop is None and calls >= a.max_calls:
                stop = "budget_tool_calls"
            if stop is None and u.get("prompt", 0) > a.max_context_tokens:
                stop = "budget_context"
    except Exception as e:  # noqa: BLE001
        error, stop = "%s: %s" % (type(e).__name__, str(e)[:500]), "error"
    wall = time.time() - t0
    g = grade(task, repo, baseline_visible(task))
    emit(event="grade", **{k: v for k, v in g.items()})
    row = {"task": task["id"], "type": task["type"], "title": task["title"], "pass": g["pass"],
           "hidden_passed": g["hidden_passed"], "hidden_total": g["hidden_total"],
           "hidden_failed": sorted(k for k, v in g["hidden"].items() if v != "pass"),
           "tool_calls": calls, "turns": turns, "tokens_in": tok["in"], "tokens_out": tok["out"],
           "cache_read_tokens": tok["cache_read"], "cache_write_tokens": tok["cache_write"],
           "cost_usd": round(cost, 5), "wall_s": round(wall, 1), "stop_reason": stop, "finished": stop == "finished",
           "summary": summary, "broke_visible": g["broke_visible"], "build_ok": g["build_ok"], "vet_clean": g["vet_clean"],
           "gofmt_clean": g["gofmt_clean"], "error": error}
    emit(event="result", row=row)
    log.close()
    shutil.rmtree(tmp, ignore_errors=True)
    return row


def cached_row(log_path: Path):
    if not log_path.exists():
        return None
    last = None
    for line in log_path.read_text().splitlines():
        ev = json.loads(line)
        if ev.get("event") == "result":
            last = ev["row"]
    return last


def cmd_run(a):
    if a.provider == "bedrock":
        import boto3
        session = boto3.Session(profile_name=a.aws_profile, region_name=a.region)
        provider_factory = lambda: Bedrock(a.model, session)  # noqa: E731
    else:
        key = open(a.key_file).read().strip() if a.key_file else os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise SystemExit("missing OPENROUTER_API_KEY (or --key-file)")
        provider_factory = lambda: OpenRouter(a.model, key)  # noqa: E731
    tasks = [t for t in load_tasks() if not a.tasks or t["id"] in a.tasks or t["id"][:2] in a.tasks]
    spend = Spend(a.max_cost_usd)
    rows = {}
    todo = []
    for t in tasks:
        lp = RUNS / a.tag / (t["id"] + ".jsonl")
        row = None if (a.only and (t["id"] in a.only or t["id"][:2] in a.only)) else cached_row(lp)
        if row:
            rows[t["id"]] = row
            spend.add(row["cost_usd"])
        else:
            todo.append((t, lp))

    def work(item):
        t, lp = item
        if spend.exceeded():
            return t["id"], None
        row = run_task(t, provider_factory(), a, spend, lp)
        print("%-34s %s  hidden %d/%d  calls %2d  $%.4f  %5.0fs  %s%s" % (
            t["id"], "PASS" if row["pass"] else "fail", row["hidden_passed"], row["hidden_total"], row["tool_calls"],
            row["cost_usd"], row["wall_s"], row["stop_reason"], "  BROKE %d visible" % len(row["broke_visible"]) if row["broke_visible"] else ""),
            flush=True)
        return t["id"], row

    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for tid, row in ex.map(work, todo):
            if row:
                rows[tid] = row
    ordered = [rows[t["id"]] for t in tasks if t["id"] in rows]
    n = len(ordered)
    totals = {"tasks": n, "passed": sum(r["pass"] for r in ordered),
              "pass_rate": round(sum(r["pass"] for r in ordered) / n, 4) if n else 0,
              "hidden_tests_passed": sum(r["hidden_passed"] for r in ordered),
              "hidden_tests_total": sum(r["hidden_total"] for r in ordered),
              "cost_usd": round(sum(r["cost_usd"] for r in ordered), 4),
              "tool_calls": sum(r["tool_calls"] for r in ordered),
              "tokens_in": sum(r["tokens_in"] for r in ordered), "tokens_out": sum(r["tokens_out"] for r in ordered),
              "wall_s": round(sum(r["wall_s"] for r in ordered), 1),
              "broke_visible_tasks": sum(bool(r["broke_visible"]) for r in ordered),
              "unclean_tasks": sum(not (r["vet_clean"] and r["gofmt_clean"]) for r in ordered),
              "skipped_for_cost_cap": [t["id"] for t in tasks if t["id"] not in rows]}
    out = {"suite": SUITE, "tag": a.tag, "model": a.model, "provider": a.provider,
           "budget": {"max_calls": a.max_calls, "max_context_tokens": a.max_context_tokens, "max_tokens_per_response": MAX_TOKENS},
           "totals": totals, "tasks": ordered}
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    path = OUTPUTS / ("%s__%s.json" % (SUITE, a.tag))
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print("wrote %s | %d/%d passed | $%.4f" % (path.relative_to(ROOT), totals["passed"], n, totals["cost_usd"]))


def cmd_verify(a):
    ok = True
    for t in load_tasks():
        if a.tasks and t["id"] not in a.tasks and t["id"][:2] not in a.tasks:
            continue
        with tempfile.TemporaryDirectory(prefix="agentic-verify-") as tmp:
            s, r = Path(tmp) / "start", Path(tmp) / "solution"
            materialize(t, s)
            materialize(t, r, "solution")
            base = baseline_visible(t)
            gs = grade(t, s, base)
            gr = grade(t, r, base)
        start_vis_fail = sorted(k for k, v in base.items() if v != "pass")
        good = (not gs["pass"] and gr["pass"] and not gr["broke_visible"] and gr["vet_clean"] and gr["gofmt_clean"]
                and gs["build_ok"] and not start_vis_fail and gr["hidden_total"] > 0)
        ok &= good
        print("%-34s %s  start: hidden %d/%d build=%s visible_fail=%d | solution: hidden %d/%d broke=%d vet=%s fmt=%s" % (
            t["id"], "OK " if good else "BAD", gs["hidden_passed"], gs["hidden_total"], gs["build_ok"], len(start_vis_fail),
            gr["hidden_passed"], gr["hidden_total"], len(gr["broke_visible"]), gr["vet_clean"], gr["gofmt_clean"]), flush=True)
        if not good and a.verbose:
            print("  start hidden:", gs["hidden"])
            print("  solution hidden:", gr["hidden"])
            print("  ", gr["diagnostics"][-1500:], gr["test_tail"][-3000:])
    raise SystemExit(0 if ok else 1)


def cmd_grade(a):
    t = next(t for t in load_tasks() if t["id"] == a.task or t["id"][:2] == a.task)
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "repo"
        shutil.copytree(a.dir, d)
        print(json.dumps(grade(t, d, baseline_visible(t)), indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify")
    v.add_argument("tasks", nargs="*")
    v.add_argument("-v", "--verbose", action="store_true")
    g = sub.add_parser("grade")
    g.add_argument("task")
    g.add_argument("dir")
    r = sub.add_parser("run")
    r.add_argument("--provider", choices=["openrouter", "bedrock"], required=True)
    r.add_argument("--model", required=True)
    r.add_argument("--tag", required=True)
    r.add_argument("--key-file")
    r.add_argument("--aws-profile")
    r.add_argument("--region", default="us-east-1")
    r.add_argument("--tasks", nargs="*", help="task ids or 2-digit prefixes (default: all)")
    r.add_argument("--only", nargs="*", help="re-run these even if a cached result exists")
    r.add_argument("--max-calls", type=int, default=40)
    r.add_argument("--max-context-tokens", type=int, default=150_000)
    r.add_argument("--max-cost-usd", type=float, default=25.0)
    r.add_argument("--jobs", type=int, default=1)
    a = ap.parse_args()
    {"verify": cmd_verify, "grade": cmd_grade, "run": cmd_run}[a.cmd](a)


if __name__ == "__main__":
    main()
