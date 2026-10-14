N = 2000

BUILTINS = "dup drop swap over rot + - * / % < = if times while call dip".split()
NAMES = ["f", "g", "sq", "loop"]


def item(rng, depth):
    r = rng.random()
    if r < 0.32:
        return [str(rng.choice([0, 1, 2, 3, -1, 5, rng.randint(-9, 20)]))] if rng.random() < 0.9 else [rng.choice(["007", "-0"])]
    if r < 0.62:
        return [rng.choice(BUILTINS)]
    if r < 0.82 and depth > 0:
        body = []
        for _ in range(rng.randint(0, 4)):
            body += item(rng, depth - 1)
        return ["["] + body + ["]"]
    if r < 0.95:
        return [rng.choice(NAMES)]
    return [rng.choice(["nope", "+1", "--", "x;", "a:b"])]


def program(rng):
    toks = []
    for _ in range(rng.randint(1, 9)):
        if rng.random() < 0.15:
            body = []
            for _ in range(rng.randint(0, 5)):
                body += item(rng, 2)
            toks += [":", rng.choice(NAMES + ["dup", "5", "["] if rng.random() < 0.1 else NAMES)] + body + [";"]
        else:
            toks += item(rng, 3)
    for _ in range(rng.choice([0, 0, 0, 0, 1, 2])):
        p = rng.randint(0, len(toks))
        if rng.random() < 0.6:
            toks.insert(p, rng.choice(["[", "]", ":", ";"]))
        elif toks:
            del toks[min(p, len(toks) - 1)]
    seps = [" ", " ", " ", "\n", "\t", ""]
    out = ""
    for t in toks:
        sep = rng.choice(seps)
        if sep == "" and not (t in "[]" or (out[-1:] in "[]")):
            sep = " "
        out += (sep if out else rng.choice(["", " "])) + t
    return out


TEMPLATES = [
    ": sq dup * ; {a} sq",
    ": fact dup 1 < [ drop 1 ] [ dup 1 - fact * ] if ; {a} fact",
    "{a} [ dup 1 - ] {b} times",
    "{a} [ dup 0 < 0 = ] [ 1 - ] while",
    "{a} {b} [ + ] dip",
    "{a} [ {b} ] dip swap",
    "1 2 3 rot over swap",
    "[ 1 2 ] call [ 3 ] [ 4 ] {a} if",
    "{a} {b} / {a} {b} %",
    "[ ] {b} times [ [ ] ] call",
    ": f [ g ] call ; : g {a} ; f : g {b} ; f",
    "{a} [ {b} < ] [ 1 + ] while",
    "[ 1 ] [ 2 ] [ 3 ] rot call",
    "{a} [ [ {b} ] dip ] call",
    ": loop {a} 0 < [ ] [ loop ] if ; loop",
    "{a} {b} = [ 7 ] [ 8 ] {c} if",
    "[ dup ] {a} times",
]


def gen(rng):
    if rng.random() < 0.5:
        return (program(rng), rng.choice([0, 3, 10, 40, 300, 300, 300]))
    parts = []
    for _ in range(rng.randint(1, 3)):
        parts.append(rng.choice(TEMPLATES).format(a=rng.randint(-2, 6), b=rng.randint(-2, 6), c=rng.choice([0, 1])))
    toks = " ".join(parts).split(" ")
    if rng.random() < 0.3:
        del toks[rng.randrange(len(toks))]
    return (" ".join(toks), rng.choice([5, 20, 60, 200, 2000]))
