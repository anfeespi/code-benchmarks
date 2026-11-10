import importlib.util, json, sys

def dec(t, x):
    k = t if isinstance(t, str) else t[0]
    if x is None or isinstance(t, str):
        return x
    if k == "optional":
        return dec(t[1], x)
    if k == "list":
        return [dec(t[1], e) for e in x]
    if k == "tuple":
        return tuple(dec(s, e) for s, e in zip(t[1:], x))
    if k == "map":
        if isinstance(x, dict) and "__pairs__" in x:
            return {dec(t[1], a): dec(t[2], b) for a, b in x["__pairs__"]}
        return {a: dec(t[2], b) for a, b in x.items()}
    return x

def enc(v):
    if isinstance(v, (list, tuple)):
        return [enc(e) for e in v]
    if isinstance(v, dict):
        if all(isinstance(a, str) for a in v):
            return {a: enc(b) for a, b in v.items()}
        return {"__pairs__": [[enc(a), enc(b)] for a, b in v.items()]}
    return v

spec = json.load(open(sys.argv[1]))
s = importlib.util.spec_from_file_location("sol", sys.argv[2])
sol = importlib.util.module_from_spec(s)
s.loader.exec_module(sol)
fn = getattr(sol, spec["entry_point"])
results = []
for call in spec["calls"]:
    args = [dec(t, a) for t, a in zip(spec["signature"]["args"], call["args"])]
    try:
        results.append({"value": enc(fn(*args))})
    except Exception:
        results.append({"error": True})
sys.stdout.write(json.dumps({"results": results}))
