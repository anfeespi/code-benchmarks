N = 600


def gen(rng):
    ops = []
    ncp = 0
    vr = rng.choice([2, 4, 8])
    for _ in range(rng.randint(0, 35)):
        x = rng.random()
        if x < 0.3:
            ops.append(("add", rng.randint(-vr, vr)))
        elif x < 0.42:
            ops.append(("remove", rng.randint(-vr - 1, vr + 1)))
        elif x < 0.57:
            ops.append(("checkpoint",))
            ncp += 1
        elif x < 0.72:
            ops.append(("rollback", rng.randint(-1, ncp + 1)))
        elif x < 0.82:
            ops.append(("median",))
        elif x < 0.92:
            ops.append(("count_less", rng.randint(-vr - 1, vr + 1)))
        else:
            ops.append(("distinct",))
    return (ops,)
