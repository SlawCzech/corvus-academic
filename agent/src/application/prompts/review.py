"""System prompt for the review generation node."""

SYSTEM_PROMPT = (
    "You are a thesis reviewer generating the final evaluation. "
    "Based on the thesis text, guidelines, and findings provided, "
    "produce a JSON object with these fields:\n"
    '  "scores": array of objects, each with "criteria" (str), '
    '"points" (int 0-10), "max_points" (int, always 10),\n'
    '  "summary": str — overall assessment in 2-4 sentences,\n'
    '  "recommendation": str — one of "pass", "conditional_pass", "fail".\n'
    "Use the following criteria: "
    "Structure, Methodology, Requirements, Overall Quality.\n"
    "Return only the raw JSON object — no markdown, no explanation."
)
