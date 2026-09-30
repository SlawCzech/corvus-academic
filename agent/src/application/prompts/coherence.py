"""Prompts for the coherence check: chapter digests (map), then one reading (reduce)."""

from src.domain.analysis import FindingSource

from .scopes import scope_instruction

_DIGEST = (
    "You read ONE part of a diploma thesis and record what it says, for a "
    "reviewer who will check the thesis as a whole from these records. Do "
    "not evaluate anything — record.\n\n"
    'Return a JSON object: {"summary": str, "claims": [{"claim": str, '
    '"quote": str}]}.\n'
    "- summary: two to four sentences — what this part does and what it "
    "argues or finds.\n"
    "- claims: up to eight of its key claims, results, numbers and "
    "conclusions, most important first. Always include every number the "
    "part reports as a result (percentages, counts, coefficients). Each has "
    "a `quote`: a passage of at most about 200 characters copied WORD FOR "
    "WORD from this part that states it.\n"
    "Return only the raw JSON object — no markdown, no explanation."
)

_COHERENCE = (
    "You check whether a diploma thesis holds together as an argument. You "
    "are given its introduction (aim, research questions, hypotheses), a "
    "digest of every part of the body in order — each with verbatim quotes "
    "— and its conclusions.\n\n"
    "Compare them. Report as findings:\n"
    "- a conclusion that the results in the body do not support, or that "
    "contradicts them (compare the numbers);\n"
    "- a research question or hypothesis from the introduction that the "
    "conclusions never answer — never state as confirmed or rejected; "
    "also when the body's results would in fact contradict it;\n"
    "- two parts of the body that contradict each other;\n"
    "- results generalised beyond the data they rest on (a small or "
    "convenience sample presented as a population).\n\n"
    "Return your findings as a JSON array. Each element has: section (str), "
    "description (str), severity (one of: critical, major, minor), "
    "suggestion (str), quote (str). A hypothesis the conclusions never "
    "address is critical; a conclusion contradicting the results is major "
    "at least. If the thesis holds together, return []. Return only the raw "
    "JSON array — no markdown, no explanation."
    + scope_instruction(FindingSource.COHERENCE)
)

_LANG_SUFFIX = {
    "pl": " Write all text fields except `quote` in Polish.",
    "en": " Write all text fields except `quote` in English.",
}


def digest_prompt(language: str = "pl") -> str:
    return _DIGEST + _LANG_SUFFIX.get(language, _LANG_SUFFIX["pl"])


def coherence_prompt(language: str = "pl") -> str:
    return _COHERENCE + _LANG_SUFFIX.get(language, _LANG_SUFFIX["pl"])
