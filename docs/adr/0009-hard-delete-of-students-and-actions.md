# ADR 0009: Hard delete of students and of single AI actions

- Status: Accepted
- Date: 2026-09-24
- Complements: [ADR 0006](0006-guideline-catalog-and-thesis-file-retention.md) (thesis file retention)

## Context

ADR 0006 set up retention: a thesis version loses its file and text on a
schedule, and keeps its row so the action history still says which version
each result was about. Nothing ever deleted a student or an action.

Two needs were not covered:

- **A student has to go now.** Added by mistake, or their data has to be
  removed, not only emptied in five months. Archiving starts the retention
  clock, but notes, AI results and the student row stay.
- **A dead action clutters the history.** Since actions can be cancelled, a run
  that died can be marked `cancelled`, but it stays in the history for good.

A plain `DELETE FROM students` would look like it works and would not. A version
points at its file (`thesis_drafts.file_id → draft_files`), not the other way
round, so no cascade from the student reaches `draft_files`: every thesis the
student handed in would be stranded there. The agent also keeps a copy of every
result (`analysis.agent_tasks.result`: whole reviews, findings, proposed topics)
in another service's schema, where `app`'s cascades do not reach at all.

## Decision

**Deleting a student removes everything, or nothing.**

1. `app` asks the agent to delete every task for the student
   (`DELETE /students/{id}/actions`). The agent revokes whatever is still running
   and deletes the rows with their results.
2. If the agent cannot be reached, `app` answers 503 and deletes nothing. The
   results live there too, so a deletion that skipped them would not be one. The
   agent's side is idempotent, so a retry is safe.
3. In one transaction, `app` deletes the versions' files through the `FileStore`
   port, the same way retention purges them, then the notes, actions, versions
   and the student. It does this with explicit statements rather than
   `ON DELETE CASCADE`. The result is the same in Postgres, and it does not depend
   on the database enforcing foreign keys (SQLite in tests does not).

The UI puts this behind typing the student's full name. For a student still
`active`, it suggests archiving instead: the everyday way to close supervision
stays retention.

**Deleting an action removes it on both sides.** The agent deletes its row first
(revoking the task if it still runs), then `app` deletes its own. A meeting note
written from the action keeps its text and loses only `source_action_id`. As with
students, an unreachable agent means 503 and nothing deleted.

Cancelling stays as a separate, gentler operation: it stops the run and keeps
the action in the history as `przerwana`.

## Rejected options

- **Soft delete (a `deleted_at` flag).** Nothing would actually leave the
  database, which is what one of the two needs is about. Every query would also
  have to remember the flag.
- **Deleting in `app` first, the agent best-effort.** Simpler and never blocked
  by the agent. But a failed call leaves full reviews of a deleted student in
  `analysis.agent_tasks` with nothing pointing at them, and nobody would notice.
- **Deleting only archived students.** A guard that protects against little: the
  typed-name confirmation already rules out a mis-click, and a student added by
  mistake is `active`.

## Consequences

- Hard delete depends on the agent being up. That is acceptable for an operation
  run by hand and rarely; the error says nothing was deleted.
- A deleted action takes its result with it. If an accepted topic came from it,
  the topic stays on the student: the decision was the promoter's, the action was
  only its source.
- The retention sweep is unchanged. It still empties versions of students who
  are kept.
