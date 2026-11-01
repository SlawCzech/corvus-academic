# ADR 0017: A one-off review is a hidden student

- Status: Accepted
- Date: 2026-11-01
- Complements: [ADR 0006](0006-guideline-catalog-and-thesis-file-retention.md) (retention), [ADR 0009](0009-hard-delete-of-students-and-actions.md) (hard delete), [ADR 0014](0014-thesis-fragments-in-rounds.md) (no student accounts)

## Context

Every action in Corvus hangs off `/students/{id}`. A promoter who has one thesis to review, often as the reviewer of someone else's student, has to invent a student first. That student then sits on the roster and in the counters for good, although nobody is being supervised.

`student_id` is `NOT NULL` on actions, thesis versions and fragments. Context assembly, ownership checks, retention and hard delete all start from a `Student`. Three shapes were considered:

| Option | Gain | Cost |
|---|---|---|
| A flag on `Student` | Polling, the pause for picking findings, cancelling, retention and delete keep working; moving to a real student is an update of one row | A "student" nobody supervises, and any new list of students has to think about the flag |
| Optional `student_id` | An honest model | Migrations on several tables, and `None` in context assembly, ownership, retention and delete, where a missed case fails quietly |
| A separate `Review` entity | The cleanest domain | The action lifecycle twice, and moving to a real student means copying rows, here and in the agent |

The project has one developer, and a one-off review is an entry into the existing flow, not a new domain.

## Decision

**A one-off review is a `Student` with `is_one_off = true`.** One thesis, one owner, the same ownership rule as any student. The promoter is the only user, and the admin does not see it (ADR 0008).

- **It is created archived.** `status = archived` and `closed_at = created_at`, so the retention sweep picks it up with no new rule. The text and file go after 150 days (ADR 0006), and the results stay. The dashboard's counters and to-do lists read only active students, so they skip it too.
- **The roster leaves it out, and name lookups do not.** The filter belongs to the roster's and to the new list's queries, not to `list_students` as a whole. The dashboard and the in-progress list use that method to name actions, and a one-off missing from it would show as `—`.
- **`POST /reviews` creates it and its thesis version, in one transaction.** It starts no action. The action runs through the existing `POST /students/{id}/actions`, so a missing key stays the existing 409 and leaves no half-made review. The frontend gets `/reviews` (the history) and `/reviews/[id]`, which reuses the action panel, the latest results and the student's delete confirmation. The form asks for the file, the author, thesis type and field of study. Title, research area and aim are optional.
- **The title page fills the form, without a model.** Choosing a file sends it to `POST /reviews/title-page`, which reads the university template's fixed places (`document/title_page.py`) and stores nothing. It fills only what is empty, and the promoter checks it, because the author and title go into the review. A model would cope with any layout, but it would need a provider before the form and would send the thesis before anyone ran anything. A title page outside the template, or a scan with no text, leaves the fields empty and the promoter types them.
- **The thesis's author is required, and `full_name` holds it.** A reviewer has the name on the title page, and the review prompt uses it to choose between "Autor" and "Autorka", defaulting to "Autorka" when it is unclear. A label such as the file name would go to the model as a person, and a blank field would make every such review "Autorka". The name also identifies the row in the history and carries over on promotion.
- **Three actions:** `generate_review`, `verify_bibliography` and `defence_questions`, which are what a reviewer needs. `app` refuses the others on a one-off. It also refuses meeting notes, fragments and a second version: a new version of the thesis is a new one-off review.
- **A real student is made by asking, never automatically.** `POST /reviews/{id}/promote` clears the flag and sets the status to `active`, which stops the retention clock. The results move with the row. A reviewer's stranger must not land on the roster, and an automatic student would be exactly the clutter this ADR removes. Promotion cannot be undone; deleting the row is the way back.
- **`PATCH /students/{id}` does not change a one-off's status.** Without this rule, reactivating one would stop its retention clock while leaving it hidden, so the thesis would never be purged.
- **Delete is ADR 0009's.** All or nothing, the agent's copies included, and 503 without the agent.
- **"One-off", not "account".** ADR 0014 stands: students have no accounts, and promotion creates a roster entry only.

## Consequences

- `Student` no longer always means someone supervised. The flag is the price of reusing the whole lifecycle, and it has to be remembered in any new list of students. If one-off reviews grow rules of their own, a separate entity becomes the better shape, and moving from this one is a data migration of known rows.
- Dashboard links still point at `/students/{id}`, and that page sends a one-off on to `/reviews/{id}`. The dashboard's API stays as it was, at the cost of one redirect in the browser. `/reviews/{id}` does the same in reverse for a promoted review.
- A one-off promoted after 150 days has its results but no text. Further actions need the thesis uploaded again, and the promotion form has to say so.
- The agent's copy of the results lives as long as the row does, with no clock of its own. A thesis may be someone else's student's, so the history shows when the text will be purged, and the promoter can delete the whole thing sooner.
- The wider privacy question from ADR 0016 applies here too: a thesis goes to the chosen provider. A reviewer often has less standing over that thesis than a supervisor has, which is one more reason to ask the university.
- The history does not group two one-offs of the same thesis. They are separate rows, and promoting one leaves the other as it was.
