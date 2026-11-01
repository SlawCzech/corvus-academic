# ADR 0018: A trial review and a final review

- Status: Accepted
- Date: 2026-11-01
- Complements: [ADR 0017](0017-a-one-off-review-is-a-hidden-student.md) (one-off reviews)

## Context

A review was one action with two jobs. A promoter wants to read a whole thesis before accepting it, and needs to know what still has to change. Later they paste a review into the university's system, where the thesis is finished and the text has to judge it. Those texts contradict each other: "wykaz literatury wymaga ujednolicenia" is what the first one is for and what the second one must never say.

The two could be one action with a parameter or two action types. The Latest Results panel shows the newest result of each type, so with a parameter a trial review would cover the final one, and a promoter could paste a text full of instructions into the university's system. That mistake is expensive, and a separate type removes it at the cost of naming the type in both services.

## Decision

- **`trial_review` is a new action; `generate_review` stays and is the final review.** Results already stored stay what they are. Some of them predate the rule against advice.
- **Same analyses, different last step.** Both run the full graph with the same findings and the same scoring. What differs is the review node's prompt.
- **A trial review tells the promoter what to fix.** It says where the thesis stands, what is good and what to correct before it is submitted, most important first. It has no tone choice, because nobody receives it as a verdict.
- **A final review judges the finished work.** No advice, no remaining work, nothing about the defence. `advice_in` rewrites it once if some slips through. The trial review skips that check, because advice is its job.
- **A trial review has its own recommendation:** "Gotowa do złożenia", "Gotowa do złożenia po poprawkach" or "Wymaga istotnych poprawek", decided by the findings as before. A MAJOR finding rules out the first, and a CRITICAL one leaves only the last.
- **A final review shows no recommendation.** The field stays in the agent, because the rule for CRITICAL findings and the status depend on it, but "Zwrócić do poprawy" means nothing for a thesis that will not change, so the page leaves it out.
- **A final review reads the accepted version.** Actions otherwise read the newest one, and a promoter can accept an older version. With no accepted version, or a purged one, it reads the newest, and the panel says which version it will read before anything runs. A warning, not a block: not every promoter marks versions.
- **The Reviews tab keeps the final review only.** `trial_review` is not in `ONE_OFF_ACTIONS`, so `app` refuses it on a one-off.

## Consequences

- Two actions run the whole graph, so a promoter who runs both pays for the analyses twice. Reusing a trial review's findings would save that, but the text they read may differ by then.
- The trial prompt needs its own evals. A prompt tuned for the final review says nothing about whether the advice is any good.
- The list in `advice_in` and the prompt rule protect different failures, and neither is a guarantee: a review is still read before it is pasted.
