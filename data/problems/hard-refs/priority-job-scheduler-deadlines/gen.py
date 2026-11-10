N = 1000


def gen(rng):
    n = rng.randint(0, 9)
    ids = rng.sample(["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "ab", "B"], n)
    jobs = []
    for jid in ids:
        r = rng.randint(0, 8)
        d = rng.randint(1, 4)
        dl = None if rng.random() < 0.5 else r + rng.randint(0, 9)
        jobs.append((jid, r, d, rng.randint(0, 3), dl))
    x = rng.random()
    if jobs and x < 0.03:
        jobs.append((jobs[0][0], 1, 1, 1, None))
    elif jobs and x < 0.05:
        jobs.append(("neg", -1, 1, 1, None))
    elif jobs and x < 0.07:
        jobs.append(("zero", 1, 0, 1, None))
    return (jobs,)


def call(mod, args):
    jobs = args[0]
    snapshot = list(jobs)
    out = mod.schedule(jobs)
    return (out, jobs == snapshot)
