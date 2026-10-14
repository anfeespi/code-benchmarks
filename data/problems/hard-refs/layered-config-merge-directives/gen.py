N = 1000

NAMES = ["a", "b", "c", "db", "max-conn", "2x", "_p", "été", 'q"t', ""]


def _scalar(rng):
    return rng.choice([0, 1, 2.5, True, False, None, "s", "", 1.0])


def _value(rng, depth):
    r = rng.random()
    if depth < 2 and r < 0.35:
        return _layer(rng, depth + 1)
    if r < 0.55:
        return [_scalar(rng) for _ in range(rng.randint(0, 2))] + ([{"-k": 1}] if rng.random() < 0.1 else [])
    return _scalar(rng)


def _layer(rng, depth):
    d = {}
    for _ in range(rng.randint(0, 4)):
        name = rng.choice(NAMES[:-1]) if rng.random() < 0.993 else ""
        kind = rng.random()
        if kind < 0.2:
            key = "-" + name
            val = None if rng.random() < 0.9 else _value(rng, depth)
        elif kind < 0.4:
            key = name + "+"
            val = [_scalar(rng) for _ in range(rng.randint(0, 2))] if rng.random() < 0.9 else _value(rng, depth)
        else:
            key = name
            val = _value(rng, depth)
        if rng.random() < 0.01:
            key = rng.choice([1, None, ("t",)])
        if rng.random() < 0.01:
            key = rng.choice(["-+", "+", "-", "a++", "--a"])
        d[key] = val
    return d


def gen(rng):
    layers = [_layer(rng, 0) for _ in range(rng.randint(0, 4))]
    if rng.random() < 0.03:
        layers.insert(rng.randint(0, len(layers)), rng.choice([[], "x", None, 3]))
    if rng.random() < 0.01:
        return (tuple(layers),)
    return (layers,)


def call(mod, args):
    import json
    snapshot = repr(args)
    merged, warnings = mod.merge_layers(*args)
    assert repr(args) == snapshot, "input mutated"
    return json.dumps([merged, warnings], ensure_ascii=False)
