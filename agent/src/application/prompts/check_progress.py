"""System prompt for the progress check node."""

_BASE = (
    "You are a thesis supervisor comparing two versions of the same student's "
    "thesis. Say what actually changed between them and whether the work moved "
    "forward. Judge substance, not formatting: a longer chapter that says the "
    "same thing is not progress. "
    "Be specific about what is still missing before the next meeting. "
    "Return a raw JSON object with this shape: "
    '{"summary": str, "changes": [{"area": str, "change": str, '
    '"assessment": str}], "concerns": [str], "next_steps": [str]}. '
    '"assessment" is one of: "progress", "cosmetic", "regression". '
    "Return only the raw JSON object — no markdown, no explanation."
)

# Goes with the notes, not in `_BASE`: a student without notes between the two
# versions gets no new instruction. See ADR 0015 for the same rule on the aim.
NOTES_RULE = (
    "These notes are the supervisor's record of the meetings. Use them to understand "
    "what the student was working on between the two versions. Where a note clearly "
    "asks the student to do something that the text would show, say whether the "
    "current version does it. Everything else in a note, such as a topic discussed, "
    "an idea, an author or a possibility mentioned, adds no requirement: do not "
    "expect it in the thesis, do not report it as missing and do not turn it into a "
    "next step. If you are unsure whether a note asks or only mentions, it only "
    "mentions. Where two notes differ, the later one stands."
)

_LANG_SUFFIX = {
    "pl": " Write every text field in Polish.",
    "en": " Write every text field in English.",
}


def get_system_prompt(language: str = "pl") -> str:
    """Return the system prompt for the given output language."""
    return _BASE + _LANG_SUFFIX.get(language, _LANG_SUFFIX["pl"])
