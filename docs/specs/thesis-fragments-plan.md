# Thesis fragments and the work timeline — implementation plan

> Status: approved and built 2026-10-31, on branch `claude/project-status-tasks-31b03f`. Decision record: [ADR 0014](../adr/0014-thesis-fragments-in-rounds.md).

## Why

A promoter works with a student in pieces: a chapter, the literature part, a
rewrite of either. Corvus only knows whole versions, so that work stays in the
mailbox and nothing shows where a student stands. Goal: record each fragment,
give direction-only feedback with AI help, and keep it on a per-student timeline.

## Scenario

1. A student mails Chapter 2. The promoter opens "Przebieg pracy" → "Dodaj
   fragment", drops the file or pastes the text, picks or types the part,
   optionally asks a question, and picks a model (or none).
2. The fragment is on the timeline at once as "czeka na feedback". With a model,
   a short summary and a feedback draft arrive when the action finishes.
3. The promoter edits the draft, picks a verdict, optionally sets the next
   deadline, saves, and copies the text into their own mail.
4. The rewrite comes in as round 2 of the same part. The draft now says whether
   the earlier feedback was acted on.

Students have no accounts, and Corvus sends no mail.

## Design in brief

### Domain (`app/src/mentoring/domain/fragment.py`)

- **`ThesisPart`:** `id`, `student_id`, `name`, `position`, `due_on: date | None`,
  `created_at`. Names are unique per student, ignoring case.
- **`ThesisFragment`:** `id`, `student_id`, `part_id`, `round_number`,
  `received_on: date`, `question`, `text`, `char_count`, `pages`, `format`
  (`pdf | docx | text`), `filename`, `file_id`, `file_sha256`, `file_size`,
  `uploaded_by`, `purged_at`, `review_action_id`, `verdict`, `feedback`,
  `feedback_at`, `feedback_source_action_id`, `created_at`.
- **`FragmentVerdict`:** `on_track` ("Na razie OK"), `needs_changes` ("Do
  poprawy"), `needs_additions` ("Do uzupełnienia"). `None` means it waits.
- **`PartState`, derived and never stored:** `not_submitted`, `awaiting_feedback`,
  or the latest round's verdict.
- `received_on` is when the student sent it, defaults to today, and cannot be in
  the future. Fragments mailed last week can be entered late.
- Rounds count per part. `feedback` may be empty: "Na razie OK" needs no comment.
- Purging follows `ThesisDraft`: text and file go; number, dates, verdict and
  feedback stay.

### Storage

Migration `0009_thesis_parts_and_fragments` in `alembic_mentoring`:

- `thesis_parts`: unique `(student_id, lower(name))`.
- `thesis_fragments`: unique `(part_id, round_number)`; `file_id` →
  `draft_files` `ON DELETE SET NULL`.
- `review_action_id` and `feedback_source_action_id` → `agent_actions`,
  `ON DELETE SET NULL`.
- Indexes for the dashboard: `thesis_parts (due_on)` and `thesis_fragments`
  filtered on `verdict IS NULL`.

Files reuse `draft_files` and the same `SqlFileStore`. No new table, and the
existing wiring in `dependencies.py` and `retention.py` carries over.

### API

All under `/students/{id}`, with the usual ownership rule (`StudentService.get`,
404 for someone else's student).

| Method and path | What it does |
|---|---|
| `POST /parts` | Add a part ahead of time, optionally with `due_on` |
| `PATCH /parts/{part_id}` | Rename, move, or set `due_on` |
| `DELETE /parts/{part_id}` | Remove an empty part; 409 if it has fragments |
| `POST /fragments` | Multipart: `part_name` (get or create), `received_on`, `question`, and `file` or `text` — exactly one |
| `GET /fragments/{id}/file` | Download the original |
| `PUT /fragments/{id}/feedback` | Set `verdict`, `feedback`, `source_action_id`, `next_due_on` |
| `DELETE /fragments/{id}` | Hard delete a mistaken upload, ADR 0009's rule |
| `GET /timeline` | `{parts, events}` — the whole "Przebieg pracy" section in one read |
| `POST /actions` | Existing endpoint; `review_fragment` requires the new `fragment_id` |

- **Upload:** the same limits and content sniffing as a thesis version
  (`MAX_UPLOAD_BYTES`, `extract`). Pasted text is capped at 200,000 characters.
  An upload clears the part's `due_on` and leaves an accepted version alone.
- **Feedback:** repeatable, because the promoter can correct it. `next_due_on`
  sets the same part's `due_on`. With `source_action_id`, the completed action is
  marked accepted, so a draft that was used is told apart from one that was not.
- **Timeline events**, newest first: fragments by `received_on`, notes by
  `occurred_at`, whole versions by `created_at`. A fragment event carries its
  summary and status from the action behind `review_action_id`. The first 400
  characters stand in when there is no summary. AI actions are not events.
- **Dashboard:** `DashboardSummary` gains `awaiting_feedback` (student, part,
  round, `received_on`) and `overdue_parts` (`due_on` before today).

### Action `review_fragment`

- Added to `ActionType` in both services, and to `_assemble`. Without
  `fragment_id` the request is a 422.
- `trigger` stores the new action's id in `review_action_id`. A rerun repoints it.
- `input_ref` holds `fragment_id` and `part_id`, and the action type stays out
  of the `ActionPanel` tiles: it starts from a fragment.
- **Context:** topic, thesis type, field of study, part name, names and states of
  the other parts, the promoter's question, the last three meeting notes, the
  fragment's text; from round 2 also the previous round's verdict, feedback and
  text, when not purged. Never the rubric, and it is not in
  `_ACTIONS_NEEDING_GUIDELINES`.
- **Graph:** one node, `review_fragment`, through `_build_single_node_graph`.
- **Reading budget:** 12,000 characters on a local model, half for each text from
  round 2. Everything on a hosted one. If cut, the prompt says so, so the model
  makes no claim about the part it did not see.
- **Reply (`replies.FRAGMENT_REVIEW`):**

  ```json
  {
    "summary": "...",
    "answer": "...",
    "direction": "on_track | needs_changes | needs_additions",
    "strengths": ["..."],
    "changes": [{"point": "...", "quote": "..."}],
    "additions": ["..."],
    "addressed": ["..."],
    "next_step": "..."
  }
  ```

- **Grounding:** a `changes` item whose quote is not in the fragment is dropped,
  using `grounding.ThesisText`, before the cap is applied. `verify_findings`
  itself does not fit: it works on `Finding`s with severities, which this action
  deliberately lacks. A direction that needs work and has none left to name
  comes back `on_track`.

### Prompt rules

The prompt lives in `prompts/review_fragment.py`. It states the level of a
diploma thesis itself: `scopes.CALIBRATION` comes with severities, which this
action deliberately has not got.

Summary:
- One or two paragraphs saying what the fragment covers and argues, neutral,
  with no judgement. It must work as a reminder of what this file was.

Feedback:
- This is work in progress and a fragment, not a thesis. The question is whether
  it is going in the right direction.
- Start with what works, and name something real.
- Answer the promoter's question first, if there is one.
- At most 3 `changes` and 3 `additions`, only about direction: fit with the
  topic, the argument, the logic, the source base, the method.
- Never report as missing what belongs to another part or may simply not be
  written yet, such as conclusions, a bibliography, or an unfinished section.
- Leave out style, typos, citation format, length, and formal requirements.
- Write tentatively ("warto rozważyć"), with no scores, severities or grades.
- `direction` defaults to `on_track`. `needs_changes` only when what is written
  would have to be rewritten, and `needs_additions` when the direction holds but
  something this part cannot do without is absent.
- From round 2: list in `addressed` what was acted on, do not repeat it, and do
  not open new minor points. If the fragment is on track, say so and stop.

### Frontend

- New section "Przebieg pracy" (`timeline`) in `StudentSubNav`, right after
  "Przegląd".
- **Part map** on top: part, rounds, state, deadline, with add, rename and move.
- **Timeline** below. A waiting fragment opens as a card with summary, question,
  editable draft, three verdict buttons, optional next deadline, and "Zapisz i
  kopiuj do maila". The rest are one line and expand on click.
- **Upload dialog:** drop zone or paste tab, part combobox with free typing,
  `received_on`, question, model picker. Same picker and default as `ActionPanel`.
  With no key the picker says the fragment will be saved without a summary.
- The upload posts the fragment and then the action as two requests, so a 409
  from the action leaves the fragment saved with "Uruchom AI" on its card.
- Unfinished actions are polled with the existing `ActionProgress` logic after a
  page reload as well.
- A pure `fragmentFeedbackDraft(output)` turns the reply into editable plain text.
- `format.ts`, `STEP_LABELS` and `ActionResultView` learn the new action, for the
  "Historia" section.
- Dashboard: "Czeka na feedback" and "Po terminie", linking to the section.

## Commits

| # | Commit | Status |
|---|---|---|
| 1 | `docs:` ADR 0014 and this spec | ✅ |
| 2 | `feat(mentoring):` parts of a thesis, and fragments handed in for them | ✅ |
| 3 | `feat(agent):` `review_fragment` — prompt, reply, node, graph | ✅ |
| 4 | `feat(mentoring):` run `review_fragment` on a fragment, with the round before it | ✅ |
| 5 | `feat(mentoring):` feedback on a fragment, and the work timeline | ✅ |
| 6 | `feat(mentoring):` retention, hard delete and the dashboard reach fragments | ✅ |
| 7 | `feat(frontend):` "Przebieg pracy" — parts, timeline, upload, feedback, dashboard | ✅ |
| 8 | `feat:` a demo student mid-writing, with parts, rounds and a missed deadline | ✅ |
| 9 | `feat(agent):` evals for `review_fragment` | ✅ |
| 10 | `fix(frontend):` a link to a student's section no longer breaks the page | ✅ |
| 11 | `docs:` CLAUDE.md, architecture, technical debt | ✅ |

## Evals

Tone is the requirement that tests cannot hold, so it is measured:

| Case | Expected |
|---|---|
| Solid literature chapter | `on_track`, nothing invented |
| Good chapter that stops mid-section, with no conclusions | `on_track`, no complaint about the ending |
| Chapter off the thesis topic | `needs_changes`, naming the mismatch |
| Round 2 that fixes one of two points | `addressed` has the fixed one, the other stays, no new minor points |

`make eval-fragments` runs them. Each run checks the caps, the absence of grades
and of harsh wording, and a judge scores whether the feedback reads as
encouragement to continue. Results in [agent/evals/README.md](../../agent/evals/README.md).

## Out of scope — next steps

- Grid calendar views and calendar export.
- Sending mail, a mail built from a whole review, and any student-facing access.
- A schedule planned in advance, beyond `due_on`.
- Moving a fragment between parts: delete and upload again.
- Feeding approved chapters into the full-thesis actions.

## Verification

- Every commit green in the touched services: `uv run pytest --cov=src` (≥80%),
  `ruff check`, `pyright src`; frontend `lint`, `typecheck`, `test`.
- Regression test: after uploading a fragment, `generate_review`, `check_progress`
  and the other document actions still read the latest whole version.
- Migrations from scratch on `pgvector/pgvector:pg16`.
- Retention: with a shifted `--now`, fragments purge with their verdict and
  feedback intact. Hard delete of a student leaves no `draft_files` rows behind.
- Smoke through `docker compose`, in the browser: new part, upload with a model,
  summary appears, save a verdict, upload round 2, its draft refers to round 1.
  Repeat with `LOCAL_MODELS_ENABLED=false` and no key: the fragment saves, no
  summary, and manual feedback works.
