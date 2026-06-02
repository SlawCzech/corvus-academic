# Corvus — review tone implementation spec

> Feature: reviewer can select the tone of the generated review.
> This spec covers all changes required across domain, agent, and frontend.

---

## Overview

Add `ReviewTone` to the domain and thread it through the entire pipeline:
metadata → state → review node → frontend upload form.

Default tone: `AUTO` — the model decides based on findings and scores.

---

## Step 1 — Domain: add ReviewTone

File: `agent/src/domain/analysis.py`

Add after `FindingSeverity`:

```python
class ReviewTone(StrEnum):
    """Tone style for the generated thesis review."""
    AUTO         = "auto"          # model decides based on findings
    ENTHUSIASTIC = "enthusiastic"  # outstanding thesis, strong praise
    POSITIVE     = "positive"      # solid work, measured tone
    DIPLOMATIC   = "diplomatic"    # meets minimum, formally positive
    NEGATIVE     = "negative"      # critical, recommends revision
```

---

## Step 2 — State: add review_tone field

File: `agent/src/application/state.py`

Add to `ThesisMetadataDict`:

```python
class ThesisMetadataDict(TypedDict):
    author:         str
    title:          str
    year:           int
    field_of_study: str
    thesis_type:    str   # "bachelor" | "master_article"
    review_tone:    str   # ReviewTone value, default "auto"
```

Add to `AnalysisState`:

```python
class AnalysisState(TypedDict):
    evaluation_id: str
    metadata:      ThesisMetadataDict
    text:          str
    guidelines:    str
    findings:      list[Finding]
    scores:        list[Score]
    review:        Review | None
    status:        str
    error:         str | None
    review_tone:   str   # propagated from metadata for convenience
```

---

## Step 3 — Review node: tone-aware prompt

File: `agent/src/application/nodes/review.py`

Replace the existing `SYSTEM_PROMPT` string with the following
implementation. Keep the file structure clean — constants at top,
function below.

```python
"""Review generation node — produces scored review with tone control."""

from __future__ import annotations

import json

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from corvus.domain.analysis import Finding, FindingSeverity, ReviewTone
from corvus.domain.review import Review, Score
from corvus.application.state import AnalysisState
from corvus.infrastructure.llm_factory import get_llm

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Base system prompt
# ---------------------------------------------------------------------------

_BASE_SYSTEM_PROMPT = """You are an academic thesis reviewer at a Polish
university of economics. Generate a formal thesis review in Polish based
on the thesis text, findings, and guidelines provided.

## Style rules

Write in formal Polish academic prose. Follow this structure exactly:

1. Opening sentence — choose based on tone instruction below.

2. Topic assessment — one sentence:
   "Podjęty temat, [topic], jest aktualny, zgodny z kierunkiem studiów
   i istotny [brief contextual justification]."

3. Research realization — one sentence describing what the author achieved
   and what methods were used (literature review, empirical analysis,
   survey, data triangulation, etc.):
   "Autorce/Autorowi udało się zrealizować przyjęte założenia badawcze,
   czemu służyły [methods used]."

4. Structure and content assessment — one sentence:
   "Dobór przedstawionych treści i przyjęta struktura są odpowiednie,
   [add specific strengths if present]."

5. Notable strength (conditional — see tone instruction).

6. Closing remark — see tone instruction.

## Language rules

- Formal Polish academic prose — no bullet points, no headers in the review
- Refer to the author as "Autorka" (female) or "Autor" (male)
  based on author name in metadata — default to "Autorka" if unclear
- One paragraph, no line breaks within the review text
- 150–250 words
- Never mention AI, analysis tools, or the review generation process
- Write as if you personally read and evaluated the thesis

## Scoring guidelines

10:   Exceptional — significantly exceeds requirements
8–9:  Good — meets all requirements, notable strengths present
6–7:  Satisfactory — meets basic requirements, minor issues only
4–5:  Weak — meets minimum, notable deficiencies present
0–3:  Failing — does not meet requirements (CRITICAL findings required)

## Output format

Return ONLY a raw JSON object — no markdown fences, no explanation:

{
  "scores": [
    {"criteria": "Struktura i spójność",      "points": <int>, "max_points": 10},
    {"criteria": "Metodologia i bibliografia", "points": <int>, "max_points": 10},
    {"criteria": "Zgodność z wymogami",        "points": <int>, "max_points": 10},
    {"criteria": "Jakość merytoryczna",        "points": <int>, "max_points": 10}
  ],
  "review_text": "<full review in Polish, one paragraph>",
  "recommendation": "<one of: 'Dopuścić do obrony' | 'Dopuścić do obrony z zastrzeżeniami' | 'Zwrócić do poprawy'>"
}

## Recommendation rules

"Dopuścić do obrony":
  No CRITICAL findings. All scores >= 6.

"Dopuścić do obrony z zastrzeżeniami":
  No CRITICAL findings. At least one score 4–5, or MAJOR findings
  that do not individually block the defense.

"Zwrócić do poprawy":
  Any CRITICAL finding present. Use regardless of tone selection.
"""

# ---------------------------------------------------------------------------
# Tone instructions — appended to base prompt depending on ReviewTone
# ---------------------------------------------------------------------------

_TONE_INSTRUCTIONS: dict[str, str] = {
    ReviewTone.AUTO: """
## Tone instruction: AUTO

Assess the findings and scores independently and select the most
appropriate tone from the options below. Apply it consistently.

- If no CRITICAL or MAJOR findings and average score >= 8: use ENTHUSIASTIC
- If no CRITICAL findings and average score 6–7: use POSITIVE
- If MAJOR findings present but no CRITICAL, average score 5–6: use DIPLOMATIC
- If any CRITICAL finding present: use NEGATIVE

Do not mention that tone was selected automatically.
""",

    ReviewTone.ENTHUSIASTIC: """
## Tone instruction: ENTHUSIASTIC

The thesis is outstanding. Reflect genuine academic appreciation.

Opening (mandatory):
  "Praca licencjacka/magisterska prezentuje wysoki poziom
  merytoryczny i formalny."

Notable strength section: MANDATORY — identify the single most
impressive aspect (methodology, source quality, original contribution,
empirical rigor) and name it explicitly.

Closing (mandatory):
  "Strona formalna oraz redakcyjna opracowania nie budzi
  żadnych zastrzeżeń."

Scores: reflect actual quality — do not inflate artificially.
Recommendation: "Dopuścić do obrony" unless CRITICAL finding forces otherwise.
""",

    ReviewTone.POSITIVE: """
## Tone instruction: POSITIVE

The thesis is solid. Professional and measured — neither cold nor warm.

Opening (mandatory):
  "Praca spełnia wymagania stawiane pracom dyplomowym."

Notable strength section: include ONLY if findings genuinely support it.
Do not invent strengths.

Closing: based on actual findings:
  - No issues: "Strona formalna oraz redakcyjna opracowania
    nie budzi żadnych zastrzeżeń."
  - Minor issues only: "W pracy obecne są niedociągnięcia formalne
    i stylistyczne nie rzutujące na odbiór prezentowanych treści."

Scores: 6–9 range depending on findings.
""",

    ReviewTone.DIPLOMATIC: """
## Tone instruction: DIPLOMATIC

The thesis meets the minimum requirements — formally positive,
but the reviewer is not impressed. Academic courtesy without praise.

Opening (mandatory):
  "Praca spełnia wymagania stawiane pracom dyplomowym."

Notable strength section: DO NOT include. The thesis has no
exceptional qualities worth highlighting.

Closing (mandatory — choose one):
  "W pracy obecne są niedociągnięcia formalne i stylistyczne
  nie rzutujące na odbiór prezentowanych treści."
  OR if substantive issues present:
  "W pracy obecne są niedociągnięcia merytoryczne nie dyskwalifikujące
  jej jako całości."

Scores: 5–7 range. Reflect the lukewarm quality honestly.
Recommendation: "Dopuścić do obrony" or "Dopuścić do obrony
z zastrzeżeniami" depending on severity of MAJOR findings.
""",

    ReviewTone.NEGATIVE: """
## Tone instruction: NEGATIVE

The thesis does not meet the required standard. The review must
clearly communicate deficiencies — formally and specifically,
without being personal or dismissive.

Opening: DO NOT use the standard positive opening.
Start directly with the core problem, for example:
  "Praca wymaga istotnych poprawek przed dopuszczeniem do obrony."
  OR name the specific critical deficiency in the opening sentence.

Body: address each CRITICAL finding by name. Be specific.
Do not soften the language beyond academic courtesy.

Notable strength section: include ONLY if a genuine strength
exists that should be acknowledged despite the overall failure.

Closing: describe what must be corrected before resubmission.

Scores: 0–5 range depending on findings.
Recommendation: MUST be "Zwrócić do poprawy".
""",
}

# ---------------------------------------------------------------------------
# Node function
# ---------------------------------------------------------------------------

def generate_review(state: AnalysisState) -> AnalysisState:
    """Generate scored review with tone-controlled Polish prose."""
    log = logger.bind(evaluation_id=state["evaluation_id"])

    try:
        tone_value = state.get("review_tone", ReviewTone.AUTO)
        tone = ReviewTone(tone_value)
        tone_instruction = _TONE_INSTRUCTIONS[tone]
        system_prompt = _BASE_SYSTEM_PROMPT + tone_instruction

        findings_text = "\n".join(
            f"- [{f.severity.upper()}] {f.section}: {f.description}"
            for f in state["findings"]
        )

        user_message = (
            f"Thesis title: {state['metadata']['title']}\n"
            f"Author: {state['metadata']['author']}\n"
            f"Type: {state['metadata']['thesis_type']}\n"
            f"Field: {state['metadata']['field_of_study']}\n\n"
            f"Findings:\n{findings_text}\n\n"
            f"Thesis text (excerpt):\n{state['text'][:8000]}"
        )

        llm = get_llm()
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])

        raw = response.content.strip()
        data = json.loads(raw)

        scores = [
            Score(
                criteria=s["criteria"],
                points=s["points"],
                max_points=s["max_points"],
            )
            for s in data["scores"]
        ]

        from uuid import uuid4
        review = Review(
            review_id=uuid4(),
            thesis_id=state["evaluation_id"],  # type: ignore[arg-type]
            scores=scores,
            summary=data["review_text"],
            recommendation=data["recommendation"],
        )

        log.info(
            "review generated",
            tone=tone,
            recommendation=review.recommendation,
            scores={s.criteria: s.points for s in scores},
        )

        return {**state, "review": review}

    except Exception as exc:
        log.error("review generation failed", error=str(exc))
        return {**state, "error": str(exc)}
```

---

## Step 4 — Frontend: tone selector in upload form

File: `frontend/components/analysis/UploadForm.tsx`

Add a radio group below the thesis type selector.
Use shadcn/ui `RadioGroup` and `RadioGroupItem`.

```tsx
// Add to form schema (Zod)
review_tone: z.enum([
  "auto",
  "enthusiastic",
  "positive",
  "diplomatic",
  "negative",
]).default("auto"),
```

UI labels:

```
Ton recenzji:
● Automatyczny — model dobiera ton na podstawie analizy  ← default
○ Entuzjastyczny — wyróżniająca, wysoka ocena
○ Pozytywny — dobra praca, bez przesady
○ Dyplomatyczny — spełnia minimum, powściągliwy
○ Negatywny — krytyczny, wymaga poprawy
```

The selected value is sent as `review_tone` in the POST /analysis
request body alongside `file`, `thesis_type`, and other metadata.

---

## Step 5 — Gateway: pass review_tone through

File: `gateway/src/infrastructure/router.py`

Add `review_tone: str = "auto"` to the analysis request schema:

```python
class AnalysisRequest(BaseModel):
    thesis_type:  str
    author:       str
    title:        str
    year:         int
    field_of_study: str
    review_tone:  str = "auto"
```

Pass it into the Celery task call:

```python
analyze_thesis.delay(
    evaluation_id=str(uuid4()),
    text=extracted_text,
    guidelines=loaded_guidelines,
    metadata={
        "author":         req.author,
        "title":          req.title,
        "year":           req.year,
        "field_of_study": req.field_of_study,
        "thesis_type":    req.thesis_type,
        "review_tone":    req.review_tone,
    },
)
```

---

## Step 6 — Celery task: propagate review_tone to state

File: `agent/src/application/tasks.py`

```python
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def analyze_thesis(
    self,
    evaluation_id: str,
    text: str,
    guidelines: str,
    metadata: dict,
) -> dict:
    initial_state: AnalysisState = {
        "evaluation_id": evaluation_id,
        "metadata":      metadata,
        "text":          text,
        "guidelines":    guidelines,
        "findings":      [],
        "scores":        [],
        "review":        None,
        "status":        EvaluationStatus.ANALYZING,
        "error":         None,
        "review_tone":   metadata.get("review_tone", "auto"),
    }
    ...
```

---

## Tests to write

File: `agent/tests/application/test_review_node.py`

```python
# Test 1 — AUTO tone selects ENTHUSIASTIC for high scores
# mock llm, all findings MINOR → verify prompt contains "wysoki poziom"

# Test 2 — AUTO tone selects NEGATIVE for CRITICAL finding
# mock llm, one CRITICAL finding → verify recommendation == "Zwrócić do poprawy"

# Test 3 — DIPLOMATIC tone suppresses notable strength
# mock llm response → verify "Na szczególne" NOT in review_text

# Test 4 — NEGATIVE tone changes opening
# mock llm → verify review_text does NOT start with "Praca spełnia"

# Test 5 — invalid tone value falls back to AUTO without crashing
# pass review_tone="invalid" → node handles ValueError gracefully

# Test 6 — JSON parse error sets state["error"]
# mock llm returning non-JSON → verify state["error"] is not None
```

---

## Commit message

```
feat(agent): add ReviewTone with AUTO default to review generation node
```

---

## Verification

```bash
uv run pytest agent/tests/application/test_review_node.py -v
uv run ruff check agent/
uv run pyright agent/
npm run typecheck   # frontend
npm run lint        # frontend
```

Manual check:
- [ ] "Automatyczny" is pre-selected on the upload form
- [ ] Changing tone selection updates the POST payload
- [ ] AUTO tone generates different openings for different quality theses
- [ ] NEGATIVE tone always produces "Zwrócić do poprawy" recommendation
