This function dispatches jobs onto a single machine. Operators report that its dispatch
log sometimes disagrees with the documented policy below, that callers have noticed side
effects on their own data after calling it, and that a full day's queue (a couple of
hundred thousand jobs) takes far too long. Find and fix the bug(s), returning a corrected
version with the exact same function name and signature (`schedule(jobs)`).

Current (buggy) implementation:

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

Contract:
- `jobs` is a list of 5-tuples `(job_id, release, duration, priority, deadline)`:
  `job_id` is a str, unique across the list; `release` is an int >= 0 (the job cannot
  start before it); `duration` is an int >= 1; `priority` is an int (higher = more
  urgent); `deadline` is an int or None (no deadline).
- Validation, checked job by job in list order before anything is scheduled: an element
  that is not a tuple of length 5, a job_id already used by an earlier job, a negative
  release, or a duration < 1 raises ValueError.
- The caller's list (and its order) must not be modified.
- Policy: there is one machine, free at time 0, and it never preempts. Whenever the
  machine is free at time T it looks at every job not yet handled whose release <= T
  (a job released exactly at T is eligible).
    * If there is none, the machine idles until the earliest release among the jobs not
      yet handled, and looks again at that time.
    * Otherwise it takes the eligible job with the highest priority; ties are broken by
      the smaller release, then by the smaller job_id (ordinary Python str comparison).
      The taken job is now handled:
        - if its deadline is not None and T + duration > deadline, the job is DROPPED: it
          takes no time, and the machine (still free at T) immediately looks again;
        - otherwise it RUNS from T to T + duration, and the machine is next free at
          T + duration.
- Return a tuple `(runs, dropped)`: `runs` lists `(job_id, start, end)` for every job that
  ran, in execution order; `dropped` lists the job_ids of dropped jobs, in the order they
  were dropped. `schedule([])` returns `([], [])`.

Performance: lists of 200,000 jobs (many of them released at the same moment) must be
scheduled in a few seconds.

Examples:
- schedule([("a", 0, 3, 1, None), ("b", 1, 2, 5, None), ("c", 3, 1, 5, None), ("d", 2, 1, 9, 3)])
    == ([("a", 0, 3), ("b", 3, 5), ("c", 5, 6)], ["d"])
  # at T=3: d (priority 9) cannot finish by 3 and is dropped; b and c tie on priority 5,
  # b has the smaller release
- schedule([("x", 5, 2, 1, None), ("y", 5, 1, 4, None), ("z", 0, 1, 0, None)])
    == ([("z", 0, 1), ("y", 5, 6), ("x", 6, 8)], [])
- schedule([("p", 0, 4, 2, None), ("q", 4, 1, 2, None), ("r", 2, 1, 2, None), ("s", 4, 2, 3, 6)])
    == ([("p", 0, 4), ("s", 4, 6), ("r", 6, 7), ("q", 7, 8)], [])
