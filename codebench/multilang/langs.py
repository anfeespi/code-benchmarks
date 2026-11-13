"""Per-language signature rendering, prompt header, and build/run commands."""
import ast
import re
import shutil
import subprocess
from pathlib import Path

from . import typesys

DRIVERS = Path(__file__).resolve().parent / "drivers"
LANGS = ("python", "go", "java", "cpp", "typescript")
JDK = Path("/opt/homebrew/opt/openjdk/bin")
INT64 = 2 ** 63
SAFE_JS = 2 ** 53


def arg_names(problem):
    for node in ast.parse(problem["canonical_solution"]).body:
        if isinstance(node, ast.FunctionDef) and node.name == problem["entry_point"]:
            return [a.arg for a in node.args.args]
    raise ValueError("entry point not found in the canonical solution")


def camel(name, upper):
    parts = name.split("_")
    head = parts[0].capitalize() if upper else parts[0]
    return head + "".join(p.capitalize() for p in parts[1:])


def entry_name(lang, ep):
    return {"go": camel(ep, True), "typescript": camel(ep, False), "java": camel(ep, False)}.get(lang, ep)


def tuples_of(sig):
    """Distinct tuple types in first-seen order; Go needs a named struct for each."""
    seen = []

    def walk(t):
        if isinstance(t, str):
            return
        for x in t[1:]:
            walk(x)
        if t[0] == "tuple" and t not in seen:
            seen.append(t)
    for t in sig["args"] + [sig["returns"]]:
        walk(t)
    return seen


def go_type(t, tuples):
    if isinstance(t, str):
        return {"int": "int", "float": "float64", "bool": "bool", "str": "string"}.get(t, "int")
    if t[0] == "list":
        return "[]" + go_type(t[1], tuples)
    if t[0] == "optional":
        return "*" + go_type(t[1], tuples)
    if t[0] == "map":
        return "map[%s]%s" % (go_type(t[1], tuples), go_type(t[2], tuples))
    return "Tuple%d" % (tuples.index(t) + 1)


def cpp_type(t):
    if isinstance(t, str):
        return {"int": "long long", "float": "double", "bool": "bool", "str": "std::string"}.get(t, "long long")
    if t[0] == "list":
        return "std::vector<%s>" % cpp_type(t[1])
    if t[0] == "optional":
        return "std::optional<%s>" % cpp_type(t[1])
    if t[0] == "map":
        return "std::map<%s, %s>" % (cpp_type(t[1]), cpp_type(t[2]))
    return "std::tuple<%s>" % ", ".join(cpp_type(x) for x in t[1:])


def java_type(t, tuples, boxed=False):
    if isinstance(t, str):
        prim = {"int": ("long", "Long"), "float": ("double", "Double"), "bool": ("boolean", "Boolean"),
                "str": ("String", "String")}.get(t, ("long", "Long"))
        return prim[1] if boxed else prim[0]
    if t[0] == "list":
        return "List<%s>" % java_type(t[1], tuples, True)
    if t[0] == "optional":
        return java_type(t[1], tuples, True)
    if t[0] == "map":
        return "Map<%s, %s>" % (java_type(t[1], tuples, True), java_type(t[2], tuples, True))
    return "Tuple%d" % (tuples.index(t) + 1)


def ts_type(t):
    if isinstance(t, str):
        return {"int": "number", "float": "number", "bool": "boolean", "str": "string"}.get(t, "number")
    if t[0] == "list":
        inner = ts_type(t[1])
        return ("(%s)[]" if "|" in inner else "%s[]") % inner
    if t[0] == "optional":
        return "%s | null" % ts_type(t[1])
    if t[0] == "map":
        if t[1] == "str":
            return "Record<string, %s>" % ts_type(t[2])
        return "Map<%s, %s>" % (ts_type(t[1]), ts_type(t[2]))
    return "[%s]" % ", ".join(ts_type(x) for x in t[1:])


def render(lang, problem, sig):
    """(signature shown to the model, extra files the harness needs)."""
    names, ep = arg_names(problem), entry_name(lang, problem["entry_point"])
    if lang == "go":
        tuples = tuples_of(sig)
        defs = "".join("type Tuple%d struct {\n%s}\n\n" % (i + 1, "".join(
            "\tF%d %s\n" % (k, go_type(x, tuples)) for k, x in enumerate(t[1:]))) for i, t in enumerate(tuples))
        ret = go_type(sig["returns"], tuples)
        if sig["raises"]:
            ret = "(%s, error)" % ret
        shown = "%sfunc %s(%s) %s" % (defs, ep, ", ".join(
            "%s %s" % (n, go_type(t, tuples)) for n, t in zip(names, sig["args"])), ret)
        return shown, {"entry.go": "package main\n\nvar entryPoint = %s\n" % ep,
                       "go.mod": "module candidate\n\ngo 1.22\n"}
    if lang == "cpp":
        params = ", ".join("const %s& %s" % (cpp_type(t), n) if not isinstance(t, str) or t == "str"
                           else "%s %s" % (cpp_type(t), n) for n, t in zip(names, sig["args"]))
        proto = "%s %s(%s)" % (cpp_type(sig["returns"]), ep, params)
        conv = ", ".join("Conv<%s>::from(args[%d])" % (cpp_type(t), i) for i, t in enumerate(sig["args"]))
        hpp = ("%s;\n\nstatic void call_entry(const std::vector<J>& args, std::string& v) {\n"
               "    auto r = %s(%s);\n    Conv<%s>::to(v, r);\n}\n#define CALL_ENTRY(args, v) call_entry(args, v)\n"
               % (proto, ep, conv, cpp_type(sig["returns"])))
        return proto + ";", {"sig.hpp": hpp}
    if lang == "java":
        tuples = tuples_of(sig)
        recs = "".join("    public record Tuple%d(%s) {}\n\n" % (i + 1, ", ".join(
            "%s f%d" % (java_type(x, tuples), k) for k, x in enumerate(t[1:]))) for i, t in enumerate(tuples))
        shown = ("import java.util.*;\n\npublic final class Solution {\n%s    public static %s %s(%s) {\n"
                 "        // ...\n    }\n}" % (recs, java_type(sig["returns"], tuples), ep, ", ".join(
                     "%s %s" % (java_type(t, tuples), n) for n, t in zip(names, sig["args"]))))
        return shown, {}
    if lang == "typescript":
        shown = "export function %s(%s): %s" % (ep, ", ".join(
            "%s: %s" % (n, ts_type(t)) for n, t in zip(names, sig["args"])), ts_type(sig["returns"]))
        return shown, {}
    return "def %s(%s)" % (ep, ", ".join(names)), {}


HEADERS = {
    "go": """Solve the problem below in Go. The statement was written for Python; translate it with these rules.

Implement exactly this, in `package main`, with no `main` function:

```go
{signature}
```

- Include the `Tuple` type definitions above in your answer, unchanged. A Python tuple in the statement is the matching struct, with fields `F0`, `F1`, ... in the order the statement lists them.
- `None` is a nil pointer. `int` is 64-bit.
{errors}- Use only the standard library.
- Answer with one ```go code block containing the complete file.
""",
    "cpp": """Solve the problem below in C++20. The statement was written for Python; translate it with these rules.

Implement exactly this function:

```cpp
{signature}
```

- A Python tuple in the statement is the `std::tuple` in the signature, with elements in the order the statement lists them. A Python `int` is `long long`. `None` is `std::nullopt`.
{errors}- Use only the standard library and include every header you need. Do not write `main`.
- Answer with one ```cpp code block containing the complete file.
""",
    "typescript": """Solve the problem below in TypeScript. The statement was written for Python; translate it with these rules.

Implement exactly this exported function:

```ts
{signature}
```

- A Python tuple in the statement is the fixed-length array in the signature, with elements in the order the statement lists them. `None` is `null`. Every integer in the tests fits in a `number` exactly.
{errors}- Use no dependencies; the file runs on Node.js with its built-in TypeScript support, so use only erasable syntax (no `enum`, no `namespace`, no parameter properties).
- Answer with one ```ts code block containing the complete file.
""",
}
HEADERS["java"] = """Solve the problem below in Java 21. The statement was written for Python; translate it with these rules.

Implement exactly this class, keeping the method signature and the records unchanged:

```java
{signature}
```

- A Python tuple in the statement is the matching record, with components `f0`, `f1`, ... in the order the statement lists them. A Python `int` is `long`. `None` is `null` (nullable values use the boxed type).
{errors}- Use only the JDK. Do not write `main`. Helper classes go inside `Solution`.
- Answer with one ```java code block containing the complete file.
"""
ERRORS = {
    "java": "- Where the statement says to raise an exception (of any type), throw `IllegalArgumentException`.\n",
    "go": "- Where the statement says to raise an exception (of any type), return a non-nil `error` and the zero value.\n",
    "cpp": "- Where the statement says to raise an exception (of any type), throw `std::invalid_argument`.\n",
    "typescript": "- Where the statement says to raise an exception (of any type), throw an `Error`.\n",
}


def prompt(lang, problem, sig):
    if lang == "python":
        # Same rule the other languages get, so all five compete on equal terms.
        return "Use only the Python standard library.\n\n---\n\n" + problem["prompt"]
    shown, _ = render(lang, problem, sig)
    head = HEADERS[lang].format(signature=shown, errors=ERRORS[lang] if sig["raises"] else "")
    return head + "\n---\n\n" + problem["prompt"]


FENCES = {"java": ("java",), "go": ("go", "golang"), "cpp": ("cpp", "c++", "cc", "cxx"), "typescript": ("ts", "typescript"),
          "python": ("python", "py")}


def extract_code(lang, text):
    """The longest block fenced in the language, as the Python harness does: an answer
    to a bug-fixing problem may quote short snippets before the full solution."""
    blocks = re.findall(r"```([A-Za-z+]*)[ \t]*\n(.*?)```", text or "", re.S)
    mine = [body for tag, body in blocks if tag.lower() in FENCES[lang]]
    if mine:
        return max(mine, key=len)
    return blocks[0][1] if blocks else (text or "")


def _big(v, limit):
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return abs(v) >= limit
    if isinstance(v, list):
        return any(_big(x, limit) for x in v)
    if isinstance(v, dict):
        return any(_big(x, limit) for x in v.values())
    return False


def portable_case(lang, case):
    """A case counts only if every call in it can be expressed with the problem's
    signature. Calls that pass a wrong type on purpose are dropped for Python too,
    so every language is graded on the same cases; integer width is the one
    per-language difference."""
    limit = {"python": None, "typescript": SAFE_JS}.get(lang, INT64)
    for call in case["calls"]:
        if call.get("typed") is False:
            return False
        if limit and (_big(call["args"], limit) or _big(call.get("value"), limit)):
            return False
    return bool(case["calls"])


def supported(lang, sig):
    return lang == "python" or not typesys.has_dynamic(sig)


def build(lang, problem, sig, code, work):
    """Write the candidate and its driver into work. Returns (run argv prefix, error or None)."""
    work = Path(work)
    _, extra = render(lang, problem, sig)
    for name, body in extra.items():
        (work / name).write_text(body)
    if lang == "python":
        (work / "solution.py").write_text(code)
        from .. import harness
        return [harness.PYTHON, str(DRIVERS / "driver.py"), "{case}", str(work / "solution.py")], None
    if lang == "typescript":
        (work / "solution.ts").write_text(code)
        shutil.copy(DRIVERS / "driver.ts", work / "driver.ts")
        return ["node", "--stack-size=65500", str(work / "driver.ts"), "{case}"], None
    if lang == "java":
        (work / "Solution.java").write_text(code)
        shutil.copy(DRIVERS / "Driver.java", work / "Driver.java")
        cmd = [str(JDK / "javac"), "-nowarn", "-d", "out", "Solution.java", "Driver.java"]
        try:
            p = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            return None, "compile timeout"
        if p.returncode != 0:
            return None, "compile error: " + (p.stderr or p.stdout).strip()[:600]
        return [str(JDK / "java"), "-Xss512m", "-XX:+UseSerialGC", "-cp", str(work / "out"), "Driver", "{case}"], None
    if lang == "go":
        (work / "solution.go").write_text(code)
        shutil.copy(DRIVERS / "driver.go", work / "driver.go")
        cmd = ["go", "build", "-o", "candidate", "."]
    else:
        (work / "solution.cpp").write_text(code)
        shutil.copy(DRIVERS / "driver.cpp", work / "driver.cpp")
        cmd = ["clang++", "-std=c++20", "-O2", "-w", '-DSIGNATURE_INCLUDE="sig.hpp"',
               "driver.cpp", "solution.cpp", "-o", "candidate"]
    try:
        p = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return None, "compile timeout"
    if p.returncode != 0:
        return None, "compile error: " + (p.stderr or p.stdout).strip()[:600]
    return [str(work / "candidate"), "{case}"], None
