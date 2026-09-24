"""System prompt for the structure analysis node."""

from src.domain.analysis import FindingSource

from .scopes import scope_instruction

_BASE = (
    "You are a thesis reviewer analyzing chapter structure and coherence "
    "of a diploma thesis. Return your findings as a JSON array. "
    "Each element must have these fields: "
    "section (str), description (str), "
    "severity (one of: critical, major, minor), suggestion (str). "
    "Return only the raw JSON array — no markdown, no explanation."
    " The thesis text may be an excerpt; the document map that comes "
    "with it lists the sections of the complete thesis. Never report a "
    "section as missing when the map lists it, and never infer that the "
    "thesis is incomplete from where the excerpt ends."
    + scope_instruction(FindingSource.STRUCTURE)
)

_LANG_SUFFIX = {
    "pl": " Write all text fields (section, description, suggestion) in Polish.",
    "en": " Write all text fields (section, description, suggestion) in English.",
}


def get_system_prompt(language: str = "pl") -> str:
    return _BASE + _LANG_SUFFIX.get(language, _LANG_SUFFIX["pl"])


# Legacy constant kept for backward compatibility.
SYSTEM_PROMPT = get_system_prompt("pl")
