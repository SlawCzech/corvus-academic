"""LangGraph node: generate final review with tone control."""

from __future__ import annotations

from uuid import UUID

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.application.excerpt import render_document_block
from src.application.replies import REVIEW
from src.application.structured import invoke_structured
from src.domain.analysis import ReviewTone, ThesisAnalysis
from src.domain.evaluation import EvaluationStatus
from src.domain.review import Review, Score
from src.infrastructure.llm_factory import get_llm

from ..state import ActionState, ReviewUpdate

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# The review node reads least of the four — it writes from findings.
_HEAD_CHARS = 8000

# ---------------------------------------------------------------------------
# Base system prompt
# ---------------------------------------------------------------------------

_BASE_SYSTEM_PROMPT = """You are an academic thesis reviewer at a Polish \
university of economics. Generate a formal thesis review in Polish based \
on the thesis text, findings, and guidelines provided.

## What you were given

The thesis text may be an excerpt, accompanied by a document map computed
from the complete thesis. A section the map lists EXISTS — never write that
it is missing, and never judge the work incomplete because the excerpt ends
where it does. Base the review on the findings and on what you can see.

Each finding is labelled with the analysis that raised it — structure,
methodology or requirements. Their scopes are separate, but should two
findings still describe the same problem, weigh it once, at the higher
severity.

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

_LANGUAGE_OVERRIDES: dict[str, str] = {
    "pl": "",
    "en": """
## Language override: ENGLISH

CRITICAL: Ignore all Polish language instructions above.
Write the entire review_text in formal English academic prose.
All sentences, phrases, and quotations must be in English.

Translate the recommendation field to English:
- "Dopuścić do obrony" → "Approved for defense"
- "Dopuścić do obrony z zastrzeżeniami" → "Approved for defense with reservations"
- "Zwrócić do poprawy" → "Returned for revision"

Translate the scores criteria labels to English:
- "Struktura i spójność" → "Structure and coherence"
- "Metodologia i bibliografia" → "Methodology and bibliography"
- "Zgodność z wymogami" → "Conformance with requirements"
- "Jakość merytoryczna" → "Substantive quality"

Opening sentences and all stylistic examples given in Polish above
must be adapted to their English equivalents in meaning and register.
""",
}


def generate_review(state: ActionState) -> ReviewUpdate:
    """Generate final review with tone and language control."""
    try:
        ctx = state["context"]
        tone_value = str(ctx.get("review_tone", ReviewTone.AUTO))
        try:
            tone = ReviewTone(tone_value)
        except ValueError:
            tone = ReviewTone.AUTO

        language: str = state.get("language", "pl")  # type: ignore[attr-defined]
        system_prompt = (
            _BASE_SYSTEM_PROMPT
            + _TONE_INSTRUCTIONS[tone]
            + _LANGUAGE_OVERRIDES.get(language, "")
        )

        findings_summary = "\n".join(
            f"- [{f.severity.upper()}] ({f.source or 'unknown'}) "
            f"{f.section}: {f.description}"
            for f in state["findings"]
        )

        # This node writes from the findings the earlier nodes produced; the
        # text is supplementary, so it reads the least of the four. What it
        # must not do is infer absence from the part it was not given, hence
        # the same map-and-rules block every other node gets.
        document = render_document_block(
            ctx, head_chars=_HEAD_CHARS, include_bibliography=False
        )

        meta: dict[str, object] = ctx.get("metadata", {})
        user_message = (
            f"Thesis title: {meta.get('title', 'Unknown')}\n"
            f"Author: {meta.get('author', 'Unknown')}\n"
            f"Type: {meta.get('thesis_type', 'bachelor')}\n"
            f"Field: {meta.get('field_of_study', 'Unknown')}\n\n"
            f"Guidelines:\n{ctx.get('guidelines', '')}\n\n"
            f"Accumulated findings:\n{findings_summary or 'None'}\n\n"
            f"{document}"
        )

        llm = get_llm(state["model"])
        reply = invoke_structured(
            llm,
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message),
            ],
            REVIEW,
            node="review",
        )
        scores: list[Score] = [
            Score(criteria=s.criteria, points=s.points, max_points=s.max_points)
            for s in reply.scores
        ]

        action_uuid = UUID(state["action_id"])
        review = Review(
            review_id=action_uuid,
            thesis_id=action_uuid,
            scores=scores,
            summary=reply.review_text,
            recommendation=reply.recommendation,
        )

        analysis = ThesisAnalysis(
            thesis_id=action_uuid,
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

        # Only this node's keys: findings are already in state, and handing
        # them back would sum them into the list a second time.
        return {
            "scores": scores,
            # The review *is* this action's structured output — same envelope
            # every other action fills, so `app` stores them all the same way.
            "output": {
                "summary": review.summary,
                "recommendation": review.recommendation,
                "total_percentage": review.total_percentage(),
            },
            "status": final_status.value,
        }
    except Exception as exc:
        logger.error("review_generation_failed", error=str(exc))
        return {"error": str(exc)}
