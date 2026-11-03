# ADR 0020: Code measures the numeric requirements, the model judges them

- Status: Accepted
- Date: 2026-11-02
- Complements: [ADR 0006](0006-guideline-catalog-and-thesis-file-retention.md) (numeric thresholds were stored and left unchecked)

## Context

Every guideline version stores its numeric requirements: minimum sources, minimum foreign-language sources, the suggested length. Nothing read them. The model got the same numbers as prose in the rubric, next to counts from the document map, and made the comparison itself.

ADR 0006 and its plan expected code to check the thresholds and write the findings. That does not survive the regulation. The length is only suggested. A project thesis may have fewer sources if project materials justify it. Netography does not count towards the minimum, and a bibliography does not always keep it apart. A finding written by a plain comparison would be wrong in each of these cases, and it would be wrong with the authority of a number.

## Decision

Code compares, and hands the model the fact. The finding and its severity stay with the model, which reads the rubric and the thesis.

- `app` sends the thresholds of the set in the context of both reviews, because only they run the requirements node. Without a guideline set nothing changes.
- `agent` compares them with the document map in `application/thresholds.py`, and only the requirements node gets the block. It states the standing (`BELOW the minimum`, `within the range`), tells the model not to recount, and says these are facts, not findings.
- The map now counts the entries that give a web address other than a DOI, and stops counting literature at a netography heading. A web address only says an entry *may* be netography, so a total that meets the minimum only with those entries is reported as exactly that.
- Foreign-language sources are not counted by code. Telling a language from a bibliography entry is reading, and a heuristic would hand the model a confident wrong number with an order not to recount. The block states the minimum and leaves the count to the model.

The comparison sits in `agent`, not `app`, because it is prompt text: it is written for one node, and the evals, which run without `app`, exercise it directly.

## Consequences

- Source counts and length are no longer the model's arithmetic. Three repeats on Claude with the seeded rubric: 22 sources gave a critical finding each time, a thesis meeting the numbers got no finding about them, and a length under the suggested range stayed minor, each time called only suggested.
- Not shown: that a real project thesis keeps its reduced source count. The one attempt added a sentence to an empirical thesis, and the model rightly read it as empirical. It needs a project thesis in the eval cases.
- The numbers in the rubric and in the thresholds are two copies an admin edits apart. If they differ, the model sees both.
- Maps stored or computed before this have no web count, and the block reads that as none.
- The foreign-language minimum stays as uncertain as a model's count of a bibliography.
