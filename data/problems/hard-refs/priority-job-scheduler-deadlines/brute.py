def schedule(jobs):
    # Written from the contract alone: every decision rescans all unhandled jobs.
    seen = set()
    for job in jobs:
        if not isinstance(job, tuple) or len(job) != 5:
            raise ValueError("each job must be a 5-tuple")
        job_id, release, duration, priority, deadline = job
        if job_id in seen:
            raise ValueError("duplicate job id %r" % (job_id,))
        seen.add(job_id)
        if release < 0:
            raise ValueError("job %r has a negative release time" % (job_id,))
        if duration < 1:
            raise ValueError("job %r has a non-positive duration" % (job_id,))
    remaining = list(jobs)
    t = 0
    runs, dropped = [], []
    while remaining:
        cands = [j for j in remaining if j[1] <= t]
        if not cands:
            t = min(j[1] for j in remaining)
            continue
        j = sorted(cands, key=lambda j: (-j[3], j[1], j[0]))[0]
        remaining.remove(j)
        if j[4] is not None and t + j[2] > j[4]:
            dropped.append(j[0])
        else:
            runs.append((j[0], t, t + j[2]))
            t += j[2]
    return runs, dropped
