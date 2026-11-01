# ADR 0019: A mail to the student is written from a trial review

- Status: Accepted
- Date: 2026-11-01
- Complements: [ADR 0014](0014-thesis-fragments-in-rounds.md) (a mail built from a whole review stayed open), [ADR 0018](0018-a-trial-review-and-a-final-review.md)

## Context

After a trial review the promoter knows what has to change, and then writes that to the student by hand. For fragments the saved feedback already is that mail. For a whole thesis the review text is not: it carries points and a recommendation meant for the promoter, and it is one dense paragraph.

The mail could be another field of the trial review, written in the same call, or an action of its own. A field costs nothing extra, but every trial review pays for a mail nobody may want, and a promoter who unticks findings or wants to add a deadline has no way to get a new draft without running the whole graph again.

## Decision

- **`draft_student_email` is its own action, one node, one model call.** Accepting changes nothing, as with the read-only actions.
- **It reads the newest finished trial review: its text and its findings, never the thesis.** The reading is already paid for, and a mail must not say what the review did not. Findings are the ones left after the promoter's pick. The action records `trial_review_id` in `input_ref`.
- **Only a trial review feeds it.** A final review judges a finished thesis and gives no advice, so there is nothing to forward. Without a finished trial review the action is a 409, like any other missing input.
- **One-off reviews take no mail.** Their author is not the promoter's student, and `trial_review` is not offered there anyway.
- **The student gets the work, not the assessment.** No points, percentages, severities, verdicts, recommendations or mention of the defence or of AI.
- **The mail avoids gendered address.** Polish forces "Pan" or "Pani", and a name does not settle it, so the prompt writes around them with forms like "proszę poprawić".
- **Corvus sends nothing.** As in ADR 0014, the promoter reads, signs and sends it from their own mail. The page shows a subject and a body to copy.

## Consequences

- A promoter pays for a second, cheap call when they want a mail, and nothing when they do not.
- The mail follows the newest trial review, not the one on screen in the history. Those differ only if a promoter opens an old result, and the action panel always shows the newest.
- A wrong finding reaches the student unless the promoter removes it, so the draft says it is a draft, and `make eval-trial` checks that the mail adds nothing to the review.
