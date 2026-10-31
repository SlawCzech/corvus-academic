# ADR 0014: Thesis fragments, reviewed in rounds

- Status: Accepted
- Date: 2026-10-31
- Extends: [ADR 0005](0005-predefined-actions-not-open-chat.md) (one more predefined action), [ADR 0006](0006-guideline-catalog-and-thesis-file-retention.md) (retention), [ADR 0009](0009-hard-delete-of-students-and-actions.md) (hard delete), [ADR 0011](0011-a-key-per-provider-chosen-per-action.md) (a provider chosen per action)

## Context

Corvus knows the two ends of writing a thesis: the topic and the whole version. Most of supervision happens in between. A student sends the literature part or the first chapter, the promoter says whether it is going in the right direction, the student comes back. Today that exchange lives in the promoter's mailbox, and nothing answers "where are we with this student?".

The existing tools do not fit. `generate_review` judges a finished thesis and would mark a chapter down for having no conclusions. `check_progress` compares two whole versions. A fragment uploaded as a `ThesisDraft` would be worse than useless: the document actions read the latest draft, so a chapter would silently become "the thesis" for the review, the methodology check and the defence questions.

The promoter is the only user. Students have no accounts and will not get them: they send work by mail, the promoter uploads it, the promoter sends the feedback back.

## Decision

- **A fragment belongs to a part of the thesis, and a part has rounds.** `ThesisPart` ("Rozdział 1", "Część literaturowa") is created on the fly while uploading, or ahead of time to hold a deadline. Each fragment is the next round of its part. A part's status is derived from its latest round and never stored.
- **Fragments are their own table, not a kind of `ThesisDraft`.** A `kind` column would make every query for "the latest version" responsible for excluding fragments, and missing one fails silently. The file store is shared; the entity is not.
- **The verdict is the promoter's.** `on_track`, `needs_changes` or `needs_additions` ("Na razie OK", "Do poprawy", "Do uzupełnienia") plus free text. AI suggests; nothing is recorded until the promoter saves. Recording feedback works without AI, so a promoter with no key loses the draft, not the feature.
- **One new action, `review_fragment`, returns a summary and a formative draft together.** The upload form runs it when the promoter picks a model. It is a second request after the upload, so a failed run or a missing key never loses the fragment. The summary is neutral and says what was handed in. The draft is deliberately gentle: it is work in progress, so no scores and no severities, a short capped list, nothing reported as missing that belongs elsewhere or simply is not written yet, and no formal requirements — the rubric is for the finished thesis.
- **The summary is read from the action's output, not copied onto the fragment.** The student's topic stays the only AI result denormalized out of `agent_actions`.
- **A round knows the one before it.** The action gets the part's previous feedback and verdict, so a second round checks whether what was asked for got done, instead of starting from zero.
- **The calendar is a timeline.** A derived view over fragments, meeting notes and thesis versions, with no event table of its own. A part may carry one optional `due_on`; a fragment for that part clears it. Across students, the dashboard shows what waits for feedback and what is overdue.
- **Retention and hard delete cover fragments.** Same clocks as non-accepted versions (ADR 0006): 30 days after a version is accepted, 150 days after the student is closed. A purged fragment keeps its row, verdict and feedback. Fragment files live in `draft_files`, so hard delete must collect them too, since no cascade from the student reaches that table. A fragment does not clear an accepted version: only a new whole version does.
- **Copying, not sending.** Feedback is copied for the promoter's own mail. Corvus sends no mail.

## Consequences

- The "email draft for the student" feature is covered for fragments: saved feedback is that email. A mail built from a whole review stays a separate question.
- A mistaken upload is deleted for real, row and file, together with its actions, under ADR 0009's rule: all or nothing, 503 without the agent. A round number can therefore be reused, but only by the round that replaces it.
- Later rounds cost more on a hosted model, because the previous round's text goes along. On the local model it shares the reading budget with the current fragment.
- "Gentle" is a property of a prompt, so unit tests cannot hold it. It needs eval cases of its own, and a prompt change can regress it.
- Fragments stay separate from whole versions. Whether chapters approved here could seed the full-thesis review is left open; the review reads only what is in the version it is given.
- One deadline per part is not a schedule. If promoters want a plan laid out in advance, it grows from `due_on` rather than replacing it.
