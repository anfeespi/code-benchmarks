def schedule(jobs):
    """Single-machine, non-preemptive priority scheduler with optional deadlines."""
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

    jobs.sort(key=lambda j: j[1])  # by release time

    def rank(job):
        job_id, release, duration, priority, deadline = job
        return (-priority, job_id, release)

    runs = []
    dropped = []
    ready = []
    clock = 0
    nxt = 0
    while nxt < len(jobs) or ready:
        # admit everything that has been released by now
        while nxt < len(jobs) and jobs[nxt][1] < clock:
            ready.append(jobs[nxt])
            nxt += 1
        if not ready:
            # machine idles until the next release
            clock = max(clock, jobs[nxt][1])
            ready.append(jobs[nxt])
            nxt += 1

        best = min(ready, key=rank)
        ready.remove(best)
        job_id, release, duration, priority, deadline = best
        if deadline is not None and clock + duration > deadline:
            dropped.append(job_id)
            continue
        runs.append((job_id, clock, clock + duration))
        clock += duration

    return runs, dropped
