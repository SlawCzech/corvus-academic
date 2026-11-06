# ADR 0010: Graph checkpoints in Postgres, and tasks acknowledged when they finish

- Status: Accepted
- Date: 2026-09-30
- Complements: [ADR 0009](0009-hard-delete-of-students-and-actions.md) (hard delete)

## Context

A review on the default local model runs for 10–15 minutes: three analyses in
parallel, a verification step, the review. Two things could throw that away:

- **The worker dies mid-run** (a restart, a deploy, the machine sleeping).
  Celery acknowledged a task as soon as a worker took it, so the task was
  gone: the action sat at `running` until someone cancelled it by hand — the
  dashboard's "probably dead" flag exists because of this.
- **Something outside a node raises** (a status write, a stream error). The
  task retried from scratch, redoing every finished analysis.

LangGraph can save the state after every step and resume a run from the last
one, given a checkpointer and a stable thread id.

## Decision

1. **Every run is checkpointed in Postgres** (`langgraph-checkpoint-postgres`,
   tables in the `analysis` schema, created by the saver's own `setup()` on the
   first run in a worker process). The thread id is the Celery task id, which a
   retry and a redelivery both keep. A run that finds pending steps under its id
   resumes with no input instead of starting over.
2. **Tasks are acknowledged when they finish** (`task_acks_late`) and handed
   back when the worker process dies (`task_reject_on_worker_lost`). Redis
   redelivers an unacknowledged task after the visibility timeout, set to 2 h —
   well above the longest run, so a slow review is never started twice.
3. **Checkpoints are deleted as soon as a run has an outcome** — completed,
   failed, or out of retries — and with the action on delete (both the single
   action and the student-wide delete of ADR 0009). They hold the graph state,
   and the state holds the thesis text.
4. **The serializer allow-lists the domain types** the state can contain
   (`Finding`, `Score` and their enums). Loading a checkpoint builds objects
   from database rows; anything else in there fails to load.
5. **Checkpoints are best-effort.** No database, or checkpoints switched off
   (`CHECKPOINTS_ENABLED=false`, as in tests and evals), and a run is exactly
   what it was before: it works, it just cannot resume.

## Consequences

- A killed worker costs the step it was on, not the review. Verified by
  killing a run inside the review node: the retry called the model for the
  review only.
- A task that kills its worker every time (out of memory on a huge thesis)
  now comes back every time instead of vanishing. Celery's retry limit does not
  count redeliveries; if this shows up, cap it with a delivery counter. (Done
  2026-11-06, see the second addendum.)
- A run in flight keeps up to one copy of the state per step (a few hundred kB
  each for a long thesis) until it ends.
- The user's own provider key is not in any checkpoint: it never enters the
  state (ADR 0004, `llm_factory`), which is what made this safe to add.

## Addendum — pausing for the promoter (same day)

Checkpoints made a second thing possible: a run that stops on purpose. With
"Pokaż mi uwagi, zanim powstanie recenzja" ticked, the review graph calls
`interrupt` in `promoter_review`, between `verify` and the review. The task
records `awaiting_input` with the findings in its result and keeps its
checkpoints; `app` shows the findings with a tick each, and
`POST /students/{id}/actions/{aid}/resume` sends the kept indices on. The
agent queues `resume_action` **under the paused task's own id**, so the
thread, the status row and a cancel's revoke keep referring to one run, and
the graph continues with `Command(resume=…)`.

- The node is in the graph whether or not the promoter asked — a pass-through
  when they did not — so the graph a run resumes into is the one it paused in.
- A paused run's checkpoints live until it is resumed, cancelled (which now
  deletes them) or deleted.
- The provider key is decrypted again for the resume; it was never stored.
- Without checkpoints there is nowhere to pause, so the flag is dropped and
  the review runs straight through.

## Addendum — runs that never end (2026-11-06)

Late acks left three ways for an action to stay `running` for good, which
mattered once the server was meant for more than a handful of promoters:

- **A task that keeps killing its worker** came back forever. The worker now
  counts deliveries of each attempt in Redis (`infrastructure/deliveries.py`,
  key per task, task id and retry number, a day's TTL). The fifth delivery of
  one attempt fails the task and drops its checkpoints instead of running.
  Four, not one: every deploy that lands mid-run hands the run back once.
  Counting fails open — no Redis, no limit.
- **A run stuck on something** held a worker slot indefinitely. Celery now has
  a soft time limit of 30 minutes, which the task records as a failure without
  a retry, and a hard one five minutes later. The visibility timeout dropped
  from 2 h to 45 minutes: it only has to stay above the hard limit, so a live
  run is never handed out twice.
- **A deploy mid-run** killed the worker after Docker's 10 s grace, and the
  unacknowledged task waited out the whole visibility timeout before anyone
  picked it up. Both composes now remap SIGTERM to Celery's cold shutdown
  (`REMAP_SIGTERM=SIGQUIT`) with a 30 s soft shutdown and a 60 s grace: short
  runs finish, long ones go back to the queue at once (checked with a real
  worker on Redis: "Restoring 1 unacknowledged message(s)").

What none of that catches — a final status write lost to a database blip, a
run killed by the hard limit, a message lost with Redis — is caught where
someone waits for it: `GET /actions/{task_id}` fails a pending or running task
whose row has not moved for 90 minutes (`domain.action.is_abandoned`). A run
touches its row at every node, so 90 minutes is past the time limit and the
visibility timeout together. A worker that gets such a task's message after
all, or a cancelled one, leaves the finished row alone and does not run it.
`watch.sh` alerts on both new outcomes.

The worker also went from two processes to four: a review holds a slot for a
few minutes, and two filled up as soon as a few promoters worked at once.
