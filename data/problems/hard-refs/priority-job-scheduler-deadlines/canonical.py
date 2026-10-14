import heapq


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

    order = sorted(jobs, key=lambda j: j[1])  # by release time; the input is left untouched

    runs = []
    dropped = []
    ready = []  # heap of (-priority, release, job_id, index into order)
    clock = 0
    nxt = 0
    while nxt < len(order) or ready:
        if not ready and order[nxt][1] > clock:
            # machine idles until the next release
            clock = order[nxt][1]
        # admit everything that has been released by now (release == clock included)
        while nxt < len(order) and order[nxt][1] <= clock:
            job_id, release, duration, priority, deadline = order[nxt]
            heapq.heappush(ready, (-priority, release, job_id, nxt))
            nxt += 1

        idx = heapq.heappop(ready)[3]
        job_id, release, duration, priority, deadline = order[idx]
        if deadline is not None and clock + duration > deadline:
            dropped.append(job_id)
            continue
        runs.append((job_id, clock, clock + duration))
        clock += duration

    return runs, dropped
