# ADR 0015: research area and agreed aim on the student

Status: accepted, 2026-10-31

## Context

A title says little about what a thesis is meant to do, and a fragment often
arrives before the introduction that would say so. "Czy idzie w dobrym kierunku"
then has nothing to be measured against. The analysis nodes knew even less: the
methodology and coherence nodes saw neither the topic nor the field.

## Decision

The student gets two optional fields, kept by the promoter:

- `research_area`: free text, such as "ekonomia instytucjonalna". One field, not
  a specialisation plus an area: the model reads both as a description, and
  splitting them changes nothing it does.
- `research_aim`: free text for the agreed aim with research questions or
  hypotheses. One field, because many theses have no hypothesis, and nothing
  checks them one by one.

They travel in the action context beside the topic, field and thesis type. The
agent renders all of these in one block (`application/brief.py`) for
`review_fragment`, `check_progress`, `defence_questions`, `evaluate_methodology`,
the review's methodology and coherence nodes, and the review itself. Structure
and requirements stay out: they judge form, not purpose.

The rule telling the model how to read them is added only when one of them is
filled in, so a student without them gets the behaviour they had.

Only the coherence node compares the thesis's stated aim with the agreed one,
at major at most, because an agreement can move on without the field being
updated. On a fragment, the aim is orientation: one part is not expected to
carry out the whole aim.

## Consequences

- An aim can make feedback harsher, and an area can invite invented requirements
  ("institutional economics must cite North"). Both are measured in
  `evals/fragment_cases`, not assumed away.
- A stale aim causes false alarms, so both fields stay editable on the card, and
  no history is kept.
- Thesis type now reaches `review_fragment`: its prompt assumes a first piece of
  research, which does not fit a master's thesis.
