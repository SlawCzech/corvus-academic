# ADR 0024: The model drafts the rubric from the regulation

- Status: Accepted
- Date: 2026-11-06
- Amends: [ADR 0008](0008-admin-and-promoter-are-separate-roles.md) (an admin keeps provider keys) and [ADR 0022](0022-every-action-runs-on-a-providers-key.md) (one action has no student)
- Builds on: [ADR 0023](0023-a-rubric-in-four-sections-and-no-default.md)

## Context

A rubric is Corvus's reading of a university's regulation, in four sections (ADR 0023). Until now an admin wrote it by hand: read the regulation, sort its rules into the sections, take the numbers out into the thresholds, add the severity rules. The two UE Katowice rubrics took about an hour each. Every university writes its rules in its own order and documents, so there is no template to fill; the reading is the work. That makes adding a university the slow step, and the one a model does well.

ADR 0022 runs every model call on a user's own key, and ADR 0008 left the admin without one: an admin ran no actions.

## Decision

- **The admin gives the university, the kind of thesis and the regulation; the model writes the rubric.** "Nowe wytyczne z regulaminu" creates the set and its first draft, stores the file as the version's original, and starts the draft. An existing set gets a new version the same way: attach the regulation, "Zbuduj rubrykę".
- **The draft is an agent action, `draft_rubric`, with no student.** `app` extracts the text (as it does for theses) and sends it with the thesis type, the university and the set's name. When the catalog has a published rubric of another set, it goes along as a model of the shape and depth, marked as not a source; the set's own previous version never does, so the draft is read from the regulation and not copied from what it replaces. The model returns the four sections, the thresholds, and doubts: what the admin should check.
- **The result lands in the draft version.** The version keeps the task id while the model reads (migration `0002_guidelines`); reading it through `GET /guidelines/admin/versions/{id}` takes the result in when the run has finished. A draft being written cannot be edited, re-drafted or published. A reply whose sections do not make a valid rubric is refused with the reason, and the draft keeps what it had. The rubric's preamble names the source file and lists the doubts.
- **Publishing stays the admin's.** Promoters see the rubric only once the admin has read it against the original and published it. Nothing is judged by a draft.
- **An admin keeps their own provider keys.** A new permission, `HOLD_PROVIDER_KEYS`, goes to both roles; the key settings need it instead of `SUBMIT_ANALYSIS`. An admin still sees no students and runs no student actions (ADR 0008).
- **A third thesis type, `master`**: a master's thesis in the usual form, next to `master_article` (UE Katowice's article). Poznań's regulation (Zarządzenie 92/2021 UEP) has no article form, and drafting its master's rubric as an article would ask for parts it never names. A title page that says "Praca magisterska" no longer suggests a type: only one that mentions an article suggests `master_article`, and otherwise the promoter picks.
- **A length the regulation gives in pages is not a threshold.** Code measures characters; the model leaves the length thresholds empty, writes the page range into the formal rules, and lists it as a doubt.
- **`make eval-rubric`** drafts from the two UE Katowice annexes and compares with the hand-written rubrics: code checks the shape, the paragraph references, that no threshold sits in the text and that the thresholds are right; a judge lists the rules missed and the rules invented, and whether questions and hypotheses were both made required.

## Consequences

- Adding a university is: add it, upload its regulation, read the draft, publish.
- The model sees only the regulation, which is a public document; no thesis is sent.
- A regulation that is a scan has no text, and the draft refuses it. One that refers to other documents (a style guide, title-page templates) gets those listed as doubts; the version still holds one source file.
- Not measured yet: `make eval-rubric MODEL=claude` needs `ANTHROPIC_API_KEY`. The prompt is judged by that run, not by the unit tests, which use a fake model.
- The dev compose now mounts `app/alembic_guidelines` and `app/scripts`, which it did not; a guideline migration used to wait for an image rebuild locally.
