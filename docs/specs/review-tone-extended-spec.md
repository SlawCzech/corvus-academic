# Corvus — extended ReviewTone spec (7 levels)

> Feature: add COMMENDABLE and RESERVED tones to ReviewTone.
> This spec covers only the delta from review-tone-spec.md.
> Implement as extension of the existing ReviewTone implementation.

---

## Overview

Add two new tones between existing levels:

```
AUTO          ← model decides (default, unchanged)
ENTHUSIASTIC  ← outstanding thesis, strong praise (unchanged)
COMMENDABLE   ← very good, worth highlighting — NEW
POSITIVE      ← solid work, meets requirements (unchanged)
DIPLOMATIC    ← meets minimum, restrained (unchanged)
RESERVED      ← meets minimum but notable weaknesses — NEW
NEGATIVE      ← critical, recommends revision (unchanged)
```

---

## Step 1 — Domain: extend ReviewTone

File: `agent/src/domain/analysis.py`

Replace the existing `ReviewTone` enum with:

```python
class ReviewTone(StrEnum):
    """Tone style for the generated thesis review."""
    AUTO         = "auto"          # model decides based on findings
    ENTHUSIASTIC = "enthusiastic"  # outstanding, exceptional quality
    COMMENDABLE  = "commendable"   # very good, worth explicit praise
    POSITIVE     = "positive"      # solid work, meets requirements
    DIPLOMATIC   = "diplomatic"    # meets minimum, no praise
    RESERVED     = "reserved"      # meets minimum, notable weaknesses
    NEGATIVE     = "negative"      # does not meet requirements
```

---

## Step 2 — Review node: add two tone instructions

File: `agent/src/application/nodes/review.py`

Add two entries to `_TONE_INSTRUCTIONS` dict.
Do NOT modify existing entries.

```python
ReviewTone.COMMENDABLE: """
## Tone instruction: COMMENDABLE

The thesis is genuinely good and deserves explicit recognition,
but does not reach the exceptional level of ENTHUSIASTIC.
The reviewer is clearly pleased without being effusive.

Opening (mandatory):
  "Praca prezentuje dobry poziom merytoryczny i formalny."
  OR if particularly strong in one dimension:
  "Praca prezentuje dobry poziom [merytoryczny/formalny],
  wyróżniając się [specific dimension]."

Notable strength section: MANDATORY — identify one specific
strength that elevates this thesis above average. Be concrete:
name the method, the source quality, the analytical approach,
or the empirical contribution.
  "Na szczególne podkreślenie zasługuje [specific achievement]."

Closing (mandatory):
  "Strona formalna oraz redakcyjna opracowania nie budzi
  żadnych zastrzeżeń."
  OR if minor issues present:
  "W pracy obecne są drobne niedociągnięcia formalne
  nie rzutujące na jej ogólnie wysoki poziom."

Scores: 7–9 range. Reflect genuine quality honestly.
Recommendation: "Dopuścić do obrony" unless CRITICAL finding
forces otherwise.
""",

ReviewTone.RESERVED: """
## Tone instruction: RESERVED

The thesis formally meets the minimum requirements but has
notable substantive or methodological weaknesses. The reviewer
acknowledges the minimum standard is met while making the
weaknesses clearly visible — without being harsh.
This is the appropriate tone when you would not recommend
distinction and want the student to be aware of the shortcomings.

Opening (mandatory):
  "Praca spełnia minimalne wymagania stawiane pracom dyplomowym,
  jednak prezentuje wyraźne słabości [merytoryczne/metodologiczne/formalne]."

Notable strength section: DO NOT include unless a specific
element genuinely stands out despite overall weakness.

Body: name the main weaknesses explicitly and specifically.
Draw directly from MAJOR findings. Be precise — not personal.

Closing (mandatory):
  "Wskazane niedociągnięcia nie dyskwalifikują pracy jako całości,
  jednak rzutują na jej ostateczną ocenę."

Scores: 4–6 range. Do not soften scores to protect the student.
Recommendation: "Dopuścić do obrony z zastrzeżeniami" in most cases.
  Use "Dopuścić do obrony" only if all scores >= 6 despite weaknesses.
  Use "Zwrócić do poprawy" only if CRITICAL finding is present.
""",
```

---

## Step 3 — Update AUTO tone logic

File: `agent/src/application/nodes/review.py`

Replace the AUTO tone instruction with updated score thresholds
that include the two new tones:

```python
ReviewTone.AUTO: """
## Tone instruction: AUTO

Assess the findings and scores independently. Select the most
appropriate tone and apply it consistently. Do not mention
that tone was selected automatically.

Selection rules (based on average score across all criteria
and severity of findings):

avg >= 9.0, no CRITICAL, no MAJOR:
  → ENTHUSIASTIC

avg 7.5–8.9, no CRITICAL, at most one MINOR:
  → COMMENDABLE

avg 6.0–7.4, no CRITICAL, MINOR findings only:
  → POSITIVE

avg 5.0–5.9, no CRITICAL, MAJOR findings present:
  → DIPLOMATIC

avg 3.5–4.9, no CRITICAL, multiple MAJOR findings:
  → RESERVED

any CRITICAL finding present:
  → NEGATIVE
""",
```

---

## Step 4 — Frontend: update tone selector

File: `frontend/components/analysis/UploadForm.tsx`

Update the Zod enum and radio group to include the two new options.

Zod schema:
```tsx
review_tone: z.enum([
  "auto",
  "enthusiastic",
  "commendable",
  "positive",
  "diplomatic",
  "reserved",
  "negative",
]).default("auto"),
```

UI radio group — seven options in this exact order:

```
Ton recenzji:
● Automatyczny — model dobiera ton na podstawie analizy       ← default
○ Entuzjastyczny — wyróżniająca, wyjątkowy poziom
○ Pochlebny — bardzo dobra, warta podkreślenia                ← NEW
○ Pozytywny — dobra praca, spełnia wymagania
○ Dyplomatyczny — spełnia minimum, bez pochwał
○ Powściągliwy — spełnia minimum, z wyraźnymi słabościami     ← NEW
○ Negatywny — nie spełnia wymagań, wymaga poprawy
```

---

## Tests to write

File: `agent/tests/application/test_review_node.py`

Add to existing test file:

```python
# Test 7 — COMMENDABLE tone includes notable strength section
# mock llm → verify "Na szczególne podkreślenie" in review_text

# Test 8 — COMMENDABLE opening differs from ENTHUSIASTIC
# mock llm → verify review_text does NOT contain "wysoki poziom"
# and DOES contain "dobry poziom"

# Test 9 — RESERVED tone includes weakness description
# mock llm, MAJOR findings present →
# verify review_text contains "minimalne wymagania"

# Test 10 — RESERVED recommendation is "Dopuścić do obrony z zastrzeżeniami"
# mock llm with MAJOR findings, no CRITICAL →
# verify recommendation == "Dopuścić do obrony z zastrzeżeniami"

# Test 11 — AUTO selects COMMENDABLE for avg 8.0, no MAJOR findings
# Test 12 — AUTO selects RESERVED for avg 4.5, MAJOR findings present
```

---

## Commit message

```
feat(agent): add COMMENDABLE and RESERVED tones to ReviewTone
```

---

## Verification

```bash
uv run pytest agent/tests/application/test_review_node.py -v
uv run ruff check agent/
uv run pyright agent/
npm run typecheck
npm run lint
```

Manual checks:
- [ ] All 7 options visible in upload form, AUTO pre-selected
- [ ] COMMENDABLE generates opening with "dobry poziom"
- [ ] RESERVED generates opening with "minimalne wymagania"
- [ ] AUTO correctly routes to COMMENDABLE / RESERVED at threshold scores
- [ ] Existing 5 tones unchanged in behavior
