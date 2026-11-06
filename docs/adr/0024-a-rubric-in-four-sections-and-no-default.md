# ADR 0024: A rubric in four sections, and no default requirements

- Status: Accepted
- Date: 2026-11-05
- Supersedes: the fallback in [ADR 0021](0021-requirements-go-into-the-prompt-whole.md) (the agent's own requirements file)
- Amends: [ADR 0006](0006-guideline-catalog-and-thesis-file-retention.md) (the rubric's shape) and [ADR 0020](0020-code-measures-the-model-judges.md) (numbers live in the thresholds alone)

## Context

Two things were wrong with how requirements reached the model.

**A default nobody chose.** A student without a guideline set was reviewed against the agent's own files, `university_requirements_*.md`. They were the June reading of UE Katowice's Zarządzenie 117/22, in English, and older than ADR 0020: they called a length "required" and made a short thesis critical, where the regulation only suggests a length. The picker called them "Corvus's default requirements", which they were not. A promoter who had not picked a set got a review judged by rules nobody had agreed to.

**One text for every question.** The rubric of a set went whole to the requirements check, the methodology analysis and the review. Each read the formal rules, the severity rules and the skills the thesis must show, whatever its own question was. The methodology node was told to stay in its scope and then handed the volume, citation and team-work rules. The review, which gets the findings already weighted, also got the severity rules, with their talk of admission to the defence. And the numbers were in two places: in the rubric's text and in the thresholds, edited apart, with nothing to notice when they disagreed.

Regulations differ between universities in order, wording and the documents they spread over. So a fixed shape cannot be expected of the regulation. It can be asked of the rubric, which is Corvus's reading of it.

## Decision

- **No default requirements.** The agent's requirements files and `load_guidelines` go. A review, a trial review and a methodology assessment need the student's guideline set; without one `app` refuses with 409 before anything is dispatched. Other actions run as before.
- **A set is chosen with the student.** The student form and the one-off review form require one. `POST /students` and `POST /reviews` accept `guideline_set_id`; a set can be changed but not removed (`null` is 422). A new thesis type still drops a set chosen for the old one, and the form asks for a new one in the same save. The API does not make a set mandatory on creation: the invariant lives where it matters, at the actions, and students added before this change have none.
- **A rubric has four sections**, as `##` headings, each exactly once: *Elementy pracy*, *Wymogi formalne*, *Co praca ma wykazać*, *Waga uchybień*. Text above them is a preamble for people. A version without them does not publish (422 naming what is missing). `app/src/guidelines/domain/rubric.py` owns the shape.
- **Each node reads its sections.** `app` sends the rubric as a mapping of the four sections. The requirements check reads the elements, the formal rules and the severity rules; the methodology analysis and the review read the elements and what the thesis must show (`agent/src/application/rubric.py`). A version published before this change arrives as one string and goes whole to every node, as before.
- **Numbers live in the thresholds.** The rubric's text names none of the thresholds' numbers and says only how to read them: the length is suggested, netography does not count, a project thesis may have fewer sources. Numbers that are not thresholds, such as the 150 words of an abstract, stay in the text.
- **The two UE Katowice rubrics are rewritten** in this shape, with the regulation's paragraph beside each rule. Two of Corvus's severity rules change: a conclusion is critical when it answers neither the research questions nor the hypotheses the thesis set, since the regulation asks for one or the other; and a citation style that departs from APA is major when systematic and minor when occasional, while critical stays for citations that do not identify the source.

## Consequences

- An AI-drafted rubric (the next step) has a fixed target: read whatever the university wrote and fill four sections, citing where each rule came from. The admin reviews it against the original before it is published.
- The guideline page renders the sections, says which action reads each, and sets the severity rules apart as Corvus's reading. The thresholds are the only place with numbers.
- After deploying, `make seed-guidelines UPDATE=1` on the server publishes the rewritten rubrics as new versions. Until then the old versions keep judging, whole. Students without a set need one picked once.
- Evals read the seeded rubrics from `app/scripts/seed_data/guidelines/`, so they judge against what a student is judged against. Only the thresholds are scaled to a condensed case, since the rubric has no numbers left to scale.
- If a university's regulation holds something important that fits none of the four sections, a fifth section is added then, not designed now.
