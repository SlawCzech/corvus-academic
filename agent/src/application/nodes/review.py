"""LangGraph node: generate final review with tone control."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from uuid import UUID

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.domain.analysis import FindingSeverity, ReviewTone, ThesisAnalysis
from src.domain.evaluation import EvaluationStatus
from src.domain.review import Review, Score
from src.infrastructure.llm_factory import get_llm

from ..state import AnalysisState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json(text: str) -> str:
    """Strip markdown code fences if present, otherwise return text as-is."""
    match = _FENCE_RE.search(text)
    return match.group(1) if match else text.strip()


# ---------------------------------------------------------------------------
# Base system prompt
# ---------------------------------------------------------------------------

_BASE_SYSTEM_PROMPT = """You are an academic thesis reviewer at a Polish \
university of economics. Generate a formal thesis review in Polish based \
on the thesis text, findings, and guidelines provided.

## Style rules

Write in formal Polish academic prose. Follow this structure exactly:

1. Opening sentence — choose based on tone instruction below.

2. Topic assessment — one sentence:
   "Podjęty temat, [topic], jest aktualny, zgodny z kierunkiem studiów \
i istotny [brief contextual justification]."

3. Research realization — one sentence describing what the author achieved \
and what methods were used (literature review, empirical analysis, \
survey, data triangulation, etc.):
   "Autorce/Autorowi udało się zrealizować przyjęte założenia badawcze, \
czemu służyły [methods used]."

4. Structure and content assessment — one sentence:
   "Dobór przedstawionych treści i przyjęta struktura są odpowiednie, \
[add specific strengths if present]."

5. Notable strength (conditional — see tone instruction).

6. Closing remark — see tone instruction.

## Language rules

- Formal Polish academic prose — no bullet points, no headers in the review
- Refer to the author as "Autorka" (female) or "Autor" (male) \
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
  No CRITICAL findings. At least one score 4–5, or MAJOR findings \
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

Assess the findings and scores independently and select the most \
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
  "Praca licencjacka/magisterska prezentuje wysoki poziom \
merytoryczny i formalny."

Notable strength section: MANDATORY — identify the single most \
impressive aspect (methodology, source quality, original contribution, \
empirical rigor) and name it explicitly.

Closing (mandatory):
  "Strona formalna oraz redakcyjna opracowania nie budzi \
żadnych zastrzeżeń."

Scores: reflect actual quality — do not inflate artificially.
Recommendation: "Dopuścić do obrony" unless CRITICAL finding forces otherwise.
""",
    ReviewTone.POSITIVE: """
## Tone instruction: POSITIVE

The thesis is solid. Professional and measured — neither cold nor warm.

Opening (mandatory):
  "Praca spełnia wymagania stawiane pracom dyplomowym."

Notable strength section: include ONLY if findings genuinely support it. \
Do not invent strengths.

Closing: based on actual findings:
  - No issues: "Strona formalna oraz redakcyjna opracowania \
nie budzi żadnych zastrzeżeń."
  - Minor issues only: "W pracy obecne są niedociągnięcia formalne \
i stylistyczne nie rzutujące na odbiór prezentowanych treści."

Scores: 6–9 range depending on findings.
""",
    ReviewTone.DIPLOMATIC: """
## Tone instruction: DIPLOMATIC

The thesis meets the minimum requirements — formally positive, \
but the reviewer is not impressed. Academic courtesy without praise.

Opening (mandatory):
  "Praca spełnia wymagania stawiane pracom dyplomowym."

Notable strength section: DO NOT include. The thesis has no \
exceptional qualities worth highlighting.

Closing (mandatory — choose one):
  "W pracy obecne są niedociągnięcia formalne i stylistyczne \
nie rzutujące na odbiór prezentowanych treści."
  OR if substantive issues present:
  "W pracy obecne są niedociągnięcia merytoryczne nie dyskwalifikujące \
jej jako całości."

Scores: 5–7 range. Reflect the lukewarm quality honestly.
Recommendation: "Dopuścić do obrony" or "Dopuścić do obrony \
z zastrzeżeniami" depending on severity of MAJOR findings.
""",
    ReviewTone.NEGATIVE: """
## Tone instruction: NEGATIVE

The thesis does not meet the required standard. The review must \
clearly communicate deficiencies — formally and specifically, \
without being personal or dismissive.

Opening: DO NOT use the standard positive opening.
Start directly with the core problem, for example:
  "Praca wymaga istotnych poprawek przed dopuszczeniem do obrony."
  OR name the specific critical deficiency in the opening sentence.

Body: address each CRITICAL finding by name. Be specific. \
Do not soften the language beyond academic courtesy.

Notable strength section: include ONLY if a genuine strength \
exists that should be acknowledged despite the overall failure.

Closing: describe what must be corrected before resubmission.

Scores: 0–5 range depending on findings.
Recommendation: MUST be "Zwrócić do poprawy".
""",
}


def generate_review(state: AnalysisState) -> AnalysisState:
    """Generate final review with tone-controlled Polish prose."""
    try:
        tone_value: str = state.get("review_tone", ReviewTone.AUTO)  # type: ignore[attr-defined]
        try:
            tone = ReviewTone(tone_value)
        except ValueError:
            tone = ReviewTone.AUTO

        system_prompt = _BASE_SYSTEM_PROMPT + _TONE_INSTRUCTIONS[tone]

        findings_summary = "\n".join(
            f"- [{f.severity.upper()}] {f.section}: {f.description}"
            for f in state["findings"]
        )

        user_message = (
            f"Thesis title: {state['metadata'].get('title', 'Unknown')}\n"  # type: ignore[attr-defined]
            f"Author: {state['metadata'].get('author', 'Unknown')}\n"  # type: ignore[attr-defined]
            f"Type: {state['metadata'].get('thesis_type', 'bachelor')}\n"  # type: ignore[attr-defined]
            f"Field: {state['metadata'].get('field_of_study', 'Unknown')}\n\n"  # type: ignore[attr-defined]
            f"Guidelines:\n{state['guidelines']}\n\n"
            f"Accumulated findings:\n{findings_summary or 'None'}\n\n"
            f"Thesis text:\n{state['text']}"
        )

        llm = get_llm(state["model"])
        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message),
            ]
        )
        raw: str | Sequence[object] = response.content  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        content: str = raw if isinstance(raw, str) else json.dumps(raw)
        data: dict[str, object] = json.loads(_extract_json(content))

        scores_data: list[dict[str, object]] = data["scores"]  # type: ignore[assignment]
        scores: list[Score] = [
            Score(
                criteria=str(
                    s.get("criteria") or s.get("criterion") or s.get("name") or s.get("category") or "Unknown"  # type: ignore[attr-defined]
                ),
                points=int(str(s.get("points") or s.get("score") or s.get("value") or 0)),  # type: ignore[attr-defined]
                max_points=int(str(s.get("max_points") or s.get("max") or s.get("maximum") or 10)),  # type: ignore[attr-defined]
            )
            for s in scores_data
        ]

        evaluation_uuid = UUID(state["evaluation_id"])
        review = Review(
            review_id=evaluation_uuid,
            thesis_id=evaluation_uuid,
            scores=scores,
            summary=str(data.get("review_text") or data.get("summary") or data.get("review") or ""),  # type: ignore[attr-defined]
            recommendation=str(data.get("recommendation") or data.get("decision") or ""),  # type: ignore[attr-defined]
        )

        analysis = ThesisAnalysis(
            thesis_id=evaluation_uuid,
            findings=state["findings"],
        )
        final_status = (
            EvaluationStatus.REJECTED
            if not analysis.is_ready_to_submit()
            else EvaluationStatus.ANALYZED
        )

        logger.info(
            "review_generated",
            tone=tone.value,
            recommendation=review.recommendation,
            status=final_status.value,
            score=review.total_percentage(),
        )

        result: AnalysisState = state.copy()
        result["scores"] = scores
        result["review"] = review
        result["status"] = final_status.value
        result["error"] = None
        return result
    except Exception as exc:
        logger.error("review_generation_failed", error=str(exc))
        result = state.copy()
        result["error"] = str(exc)
        return result
