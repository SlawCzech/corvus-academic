"""LangGraph node: generate final review with tone control."""

from __future__ import annotations

import re
from uuid import UUID

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.application.brief import render_research
from src.application.excerpt import render_document_block
from src.application.replies import (
    RECOMMENDATIONS,
    TRIAL_RECOMMENDATIONS,
    review_reply_for,
)
from src.application.scoring import score_bands, within_band
from src.application.structured import invoke_structured
from src.domain.action import ActionType
from src.domain.analysis import Finding, FindingSeverity, ReviewTone, ThesisAnalysis
from src.domain.evaluation import EvaluationStatus
from src.domain.review import Review, Score
from src.infrastructure.llm_factory import get_llm
from src.infrastructure.provider_errors import raise_if_provider_error

from ..state import ActionState, ReviewUpdate

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Base system prompt
# ---------------------------------------------------------------------------

_REVIEWER = """You are an academic thesis reviewer at a Polish \
university of economics. Generate a formal thesis review in Polish based \
on the thesis text, findings, and guidelines provided.

"""

_WHAT_YOU_WERE_GIVEN = """## What you were given

The thesis text may be an excerpt, accompanied by a document map computed
from the complete thesis. A section the map lists EXISTS — never write that
it is missing, and never judge the work incomplete because the excerpt ends
where it does. Base the review on the findings and on what you can see.

Each finding is labelled with the analysis that raised it — structure, coherence,
methodology or requirements. Their scopes are separate, but should two
findings still describe the same problem, weigh it once, at the higher
severity.

"""

_FINAL_STYLE = """## Style rules

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
- Refer to the author with the word given as "Author form" (Autorka or \
Autor). The text names the author and the promoter only as [autor] and \
[promotor]: never repeat a marker in the review
- One paragraph, no line breaks within the review text
- 150–250 words
- Never mention AI, analysis tools, or the review generation process
- Write as if you personally read and evaluated the thesis

## This text is a final assessment

The thesis is finished and will not be changed. review_text is pasted as it \
stands into the university's system, as the reviewer's assessment of the work. \
It says what the work is, never what should happen to it. This section \
overrides every tone instruction below.

- State each weakness as a fact about the thesis as submitted. Findings are \
often worded as fixes: turn them into what the thesis lacks or does poorly.
- No advice and no remaining work: nothing the author should add, correct, \
unify or extend, whether worded as a recommendation, a need or a plan.
- Nothing about the defence: what should be asked, answered or discussed there, \
or whether the thesis should go to it. The recommendation has its own field \
and stays out of review_text.

Not: "Baza źródłowa jest wąska, wykaz literatury wymaga ujednolicenia, a wstęp \
– uzupełnienia o charakterystykę literatury. Zalecam odniesienie się do tych \
kwestii podczas obrony."
But: "Baza źródłowa jest wąska, wykaz literatury jest niejednolity, a wstęp nie \
charakteryzuje wykorzystanej literatury."

"""

_SCORING = """## Scoring guidelines

Score against what a diploma thesis at a regional university is expected to
be, not against a journal article. Weigh the findings, do not count them.
The findings decide the range each criterion may take; the ranges come with
the findings, and they override any score range a tone instruction names.
Choose within the range.

8–10: Good to exceptional — no MAJOR finding in this criterion
7–8:  Satisfactory — a MAJOR finding in this criterion
6–7:  Satisfactory with reservations — several MAJOR findings in it
0–5:  Does not meet requirements — a CRITICAL finding in this criterion

"""

_FINAL_OUTPUT = """## Output format

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
  No CRITICAL findings. All scores >= 7.

"Dopuścić do obrony z zastrzeżeniami":
  No CRITICAL findings. At least one score of 6, or MAJOR findings \
that weigh on the assessment.

"Zwrócić do poprawy":
  Any CRITICAL finding present. Use regardless of tone selection.
"""

_BASE_SYSTEM_PROMPT = (
    _REVIEWER + _WHAT_YOU_WERE_GIVEN + _FINAL_STYLE + _SCORING + _FINAL_OUTPUT
)

# ---------------------------------------------------------------------------
# Trial review — the same findings, for a thesis that can still change
# ---------------------------------------------------------------------------

_TRIAL_REVIEWER = """You are a thesis supervisor at a Polish university of \
economics. The thesis below is not submitted yet. Write a trial review in \
Polish: you read it to decide what the author still has to do before you \
accept it.

"""

_TRIAL_STYLE = """## What to write

Formal Polish, plain and direct. Say, in this order:

1. Where the thesis stands as a whole, in one or two sentences.
2. What already works, naming it. Do not invent strengths.
3. What to correct before submission, most important first: where in the \
thesis, what is wrong and what to do about it. Draw on the findings; a finding \
that does not matter to the outcome can stay out.

The thesis is still changing, so this text is the place for advice: name the \
work that remains, concretely enough to act on. Nothing about the defence.

## Language rules

- No bullet points and no headers in the review
- Refer to the author with the word given as "Author form" (Autorka or \
Autor). The text names the author and the promoter only as [autor] and \
[promotor]: never repeat a marker in the review
- One paragraph, no line breaks within the review text
- 200–350 words
- Never mention AI, analysis tools, or the review generation process

"""

_TRIAL_OUTPUT = """## Output format

Return ONLY a raw JSON object — no markdown fences, no explanation:

{
  "scores": [
    {"criteria": "Struktura i spójność",      "points": <int>, "max_points": 10},
    {"criteria": "Metodologia i bibliografia", "points": <int>, "max_points": 10},
    {"criteria": "Zgodność z wymogami",        "points": <int>, "max_points": 10},
    {"criteria": "Jakość merytoryczna",        "points": <int>, "max_points": 10}
  ],
  "review_text": "<full review in Polish, one paragraph>",
  "recommendation": "<one of the recommendations allowed below>"
}

The points say how the thesis would score if it were submitted as it stands.
"""

_TRIAL_SYSTEM_PROMPT = (
    _TRIAL_REVIEWER + _WHAT_YOU_WERE_GIVEN + _TRIAL_STYLE + _SCORING + _TRIAL_OUTPUT
)

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
distinction and want the shortcomings on the record.

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
  "Praca nie spełnia wymagań stawianych pracom dyplomowym."
  OR name the specific critical deficiency in the opening sentence.

Body: address each CRITICAL finding by name. Be specific. \
Do not soften the language beyond academic courtesy.

Notable strength section: include ONLY if a genuine strength \
exists that should be acknowledged despite the overall failure.

Closing: say what the deficiencies mean for the assessment of the work, \
for example:
  "Wskazane braki przesądzają o negatywnej ocenie pracy."

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
- "Gotowa do złożenia" → "Ready to submit"
- "Gotowa do złożenia po poprawkach" → "Ready to submit after corrections"
- "Wymaga istotnych poprawek" → "Needs substantial corrections"

Translate the scores criteria labels to English:
- "Struktura i spójność" → "Structure and coherence"
- "Metodologia i bibliografia" → "Methodology and bibliography"
- "Zgodność z wymogami" → "Conformance with requirements"
- "Jakość merytoryczna" → "Substantive quality"

Opening sentences and all stylistic examples given in Polish above
must be adapted to their English equivalents in meaning and register.
""",
}


# Wording that tells someone what to do, or plans the defence, instead of
# judging a finished work. Wider than it needs to be on purpose: a false alarm
# costs one rewrite and nothing is thrown away.
_ADVICE = re.compile(
    r"zalecam|zaleca się|zalecane|rekomenduję|rekomenduje się|sugeruję|proponuję"
    r"|powinn\w+(?!\s+by[łl])|powinien(?!\s+by[łl])"
    r"|należy\s+(?:uzupełnić|poprawić|ujednolicić|rozszerzyć|dodać|zmienić"
    r"|usunąć|przeredagować|odnieść)"
    r"|wymag\w+\s+(?:\w+\s+)?(?:uzupełni|popraw|ujednolic|rozszerz|przeredag"
    r"|dopracow|zmian|korekt)"
    r"|do\s+(?:poprawy|uzupełnienia|ujednolicenia)"
    r"|(?:podczas|w trakcie|w czasie|przed|na)\s+obron(?:y|ą|ie)\b"
    r"|(?:dopuszcz\w+|przygotow\w+)\s+(?:\w+\s+)?do\s+obrony"
    r"|\bi recommend\b|\bshould\b|\bmust be\b"
    r"|\b(?:during|before|at) the defen[cs]e\b",
    re.IGNORECASE,
)

_REWRITE_PROMPT = """This review_text still tells someone what to do, or talks \
about the defence, in these words: {phrases}

{text}

The thesis is finished and will not be changed, so state each weakness as a \
fact about it. Reply again with the same JSON: the same scores and \
recommendation, with only review_text rewritten and everything it says about \
the work kept."""


def advice_in(text: str) -> list[str]:
    """The phrases that tell someone what to do instead of judging the work."""
    return [match.group(0) for match in _ADVICE.finditer(text)]


def allowed_recommendations(
    findings: list[Finding], language: str = "pl", trial: bool = False
) -> tuple[str, ...]:
    """What the recommendation rules leave open, given the findings.

    Any CRITICAL finding returns the thesis; without one, the choice between
    admitting it with or without reservations is the reviewer's, from the
    scores. A trial review has its own three, and a MAJOR finding means the
    thesis is not ready as it stands.
    """
    severities = {f.severity for f in findings}
    if trial:
        ready, after_corrections, needs_work = TRIAL_RECOMMENDATIONS.get(
            language, TRIAL_RECOMMENDATIONS["pl"]
        )
        if FindingSeverity.CRITICAL in severities:
            return (needs_work,)
        if FindingSeverity.MAJOR in severities:
            return (after_corrections,)
        return (ready, after_corrections)
    admit, admit_with_reservations, return_it = RECOMMENDATIONS.get(
        language, RECOMMENDATIONS["pl"]
    )
    if FindingSeverity.CRITICAL in severities:
        return (return_it,)
    return (admit, admit_with_reservations)


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
        trial = state["action_type"] == ActionType.TRIAL_REVIEW
        system_prompt = (
            _TRIAL_SYSTEM_PROMPT
            if trial
            else _BASE_SYSTEM_PROMPT + _TONE_INSTRUCTIONS[tone]
        ) + _LANGUAGE_OVERRIDES.get(language, "")

        findings = state["findings"]
        allowed = allowed_recommendations(findings, language, trial=trial)
        findings_summary = "\n".join(
            f"- [{f.severity.upper()}] ({f.source or 'unknown'}) "
            f"{f.section}: {f.description}"
            for f in state["findings"]
        )

        # This node writes from the findings the earlier nodes produced; the
        # text is there so it can check them against the work.
        document = render_document_block(ctx)

        meta: dict[str, object] = ctx.get("metadata", {})
        user_message = (
            f"Thesis title: {meta.get('title', 'Unknown')}\n"
            f"Author form: {meta.get('author_form', 'Autorka')}\n"
            f"Type: {meta.get('thesis_type', 'bachelor')}\n"
            f"Field: {meta.get('field_of_study', 'Unknown')}\n"
            f"{render_research(ctx)}\n"
            f"Guidelines:\n{ctx.get('guidelines', '')}\n\n"
            f"Accumulated findings:\n{findings_summary or 'None'}\n\n"
            f"Allowed recommendation (decided by the findings): "
            f"{' | '.join(allowed)}\n"
            f"Allowed points per criterion, in the order of the output "
            f"format (decided by the findings): "
            f"{', '.join(f'{low}–{high}' for low, high in score_bands(findings))}"
            f"\n\n"
            f"{document}"
        )

        llm = get_llm()
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]
        shape = review_reply_for(allowed)
        reply = invoke_structured(llm, messages, shape, node="review")
        # Advice is a trial review's job. In a final one the prompt forbids it,
        # but a hosted model still slips now and then,
        # and that text goes to the university as it stands. One rewrite, then
        # what there is: the phrase list can be wrong about a thesis on
        # national defence, and that must not cost a finished review.
        advice = [] if trial else advice_in(reply.review_text)
        if advice:
            logger.info("review_advice_rewritten", phrases=advice)
            reply = invoke_structured(
                llm,
                [
                    *messages,
                    HumanMessage(
                        content=_REWRITE_PROMPT.format(
                            phrases=", ".join(advice), text=reply.review_text
                        )
                    ),
                ],
                shape,
                node="review",
            )
            left = advice_in(reply.review_text)
            if left:
                logger.warning("review_advice_kept", phrases=left)
        # The prompt gives the model these ranges; this is what holds if it
        # scores outside them anyway.
        bands = score_bands(findings, len(reply.scores))
        scores: list[Score] = [
            Score(
                criteria=s.criteria,
                points=within_band(s.points, s.max_points, band),
                max_points=s.max_points,
            )
            for s, band in zip(reply.scores, bands, strict=True)
        ]
        proposed = [s.points for s in reply.scores]
        if proposed != [s.points for s in scores]:
            logger.info(
                "review_scores_held_to_findings",
                proposed=proposed,
                kept=[s.points for s in scores],
            )

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
        raise_if_provider_error(exc)
        logger.error("review_generation_failed", error=str(exc))
        return {"error": str(exc)}
