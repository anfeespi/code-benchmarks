N = 1500

VALUES = ["1", "-0", "007", "-12", "0", "true", "false", "null", "True", "x", "a b", "a: b", "# not a comment",
          '"q"', '"a\\"b"', '"tab\\there"', '""', '"\\\\"', "-", "- y", "1.5", "+3",
          "v  ", "  w", "\t", "k:v", '"x#: y"']
BAD = ['"x\\q"', '"open', '"a"b', "\"", '"end\\', '"a\\"']


def val(rng):
    return rng.choice(BAD) if rng.random() < 0.08 else rng.choice(VALUES)
KEYS = ["a", "b", "key_1", "Zed", "x-y", "_", "a", "b"]


def render(rng, depth, ind, step, out):
    kind = rng.choice(["M", "L"])
    for _ in range(rng.randint(1, 3)):
        head = (rng.choice(KEYS) + ":") if kind == "M" else "-"
        if depth > 0 and rng.random() < 0.35:
            out.append(" " * ind + head + rng.choice(["", " ", "  "]))
            if rng.random() < 0.85:
                render(rng, depth - 1, ind + rng.choice([step, step, 1, 3]), step, out)
        else:
            out.append(" " * ind + head + " " + val(rng))
        if rng.random() < 0.15:
            out.append(rng.choice(["", "   ", "\t", "# c", "\t# c", "  #"]))


def gen(rng):
    out = []
    render(rng, rng.randint(0, 3), 0, rng.choice([2, 4]), out)
    for _ in range(rng.choice([0, 0, 1, 1, 2])):
        if not out:
            break
        i = rng.randrange(len(out))
        m = rng.random()
        if m < 0.15:
            out[i] = rng.choice([" ", "  ", "\t", " \t"]) + out[i]
        elif m < 0.3:
            out[i] = out[i][1:] if out[i].startswith(" ") else " " + out[i]
        elif m < 0.38:
            t = out[i].lstrip(" ")
            out[i] = out[i][:len(out[i]) - len(t)] + ("- " + t if not t.startswith("-") else "k" + t[1:].replace(" ", ": ", 1))
        elif m < 0.45:
            out[i] = out[i].lstrip(" ")
        elif m < 0.6:
            out.insert(i, out[i])
        elif m < 0.75:
            out[i] = out[i].replace(":", " :", 1) if rng.random() < 0.5 else out[i].replace(": ", ":", 1)
        elif m < 0.9:
            out[i] = out[i][:-1]
        else:
            out[i] = out[i].replace("-", "-x", 1)
    sep = "\n"
    s = sep.join(out)
    if rng.random() < 0.2:
        s += "\n"
    return (s,)
