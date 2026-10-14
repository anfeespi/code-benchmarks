N = 1500

PIECES = ["x", "foo_1", "_a", "e", "E", "e5", "12", "007", "3.5", "1.", "2e", "2e+", "4E-2", "6e+3x", "1.5e", "9.e1",
          ".", "->", "-", ">", "-->", "==", "=", "!=", "!", "<=", "<", ">=", "(", ")", ",", "*", "/", "+",
          '"hi"', '"a\\"b"', '"t\\tn\\n"', '"\\\\"', '"bad\\q"', '"open', '"x\\', '""', "@", "\r", "é",
          "#c", "# note\n"]
SEPS = ["", "", " ", "  ", "\t", "\n", " \n ", "\n\n"]
RISKY = ("@", "\r", "é", '"bad\\q"', '"open', '"x\\', "!", ".", "1.", "9.e1")


def gen(rng):
    if rng.random() < 0.15:
        alphabet = 'ab_e1209.+-<>=!"\\#nt \n\t()*/,@'
        return ("".join(rng.choice(alphabet) for _ in range(rng.randint(0, 25))),)
    parts = []
    for _ in range(rng.randint(0, 12)):
        p = rng.choice(PIECES)
        # keep most inputs error-free so the success path is exercised often
        if rng.random() < 0.7 and p in RISKY:
            p = "y"
        parts.append(p)
        parts.append(rng.choice(SEPS))
    return ("".join(parts),)
