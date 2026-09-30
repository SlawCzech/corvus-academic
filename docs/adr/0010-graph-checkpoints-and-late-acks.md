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
  count redeliveries; if this shows up, cap it with a delivery counter.
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
