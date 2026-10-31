"""What is known about a thesis besides its text, as one block for the model.

The research area and the agreed aim are optional, and the rule for reading
them comes with them: a student without them gets no new instruction. See
ADR 0015.
"""

from typing import Any, cast

_AS_CONTEXT = (
    "The research area and the agreed aim come from the supervisor. Use them to "
    "understand what this thesis sets out to do and what is usual in its area. "
    "They add no requirements: do not expect a particular author, school, theory "
    "or method because of them, and do not report one as missing."
)


def render_research(ctx: dict[str, Any], reading: str = "") -> str:
    """The area and the aim with how to read them, or nothing if neither is set."""
    lines: list[str] = []
    if ctx.get("research_area"):
        lines.append(f"Research area: {ctx['research_area']}")
    if ctx.get("research_aim"):
        lines.append(f"Agreed aim and hypotheses:\n{ctx['research_aim']}")
    if not lines:
        return ""
    return "\n".join([*lines, _AS_CONTEXT, *([reading] if reading else [])]) + "\n"


def render_brief(ctx: dict[str, Any], reading: str = "") -> str:
    """Topic, field and type, followed by the research block when there is one.

    `reading` is what this node should do with the aim, beyond the general rule.
    The review's context keeps the first three under `metadata`.
    """
    meta = cast(dict[str, Any], ctx.get("metadata") or {})
    topic = ctx.get("current_topic") or meta.get("title") or "not settled yet"
    field = ctx.get("field_of_study") or meta.get("field_of_study") or "unspecified"
    thesis_type = ctx.get("thesis_type") or meta.get("thesis_type") or "bachelor"
    lines = [
        f"Thesis topic: {topic}",
        f"Field of study: {field}",
        f"Thesis type: {thesis_type}",
    ]
    research = render_research(ctx, reading)
    return "\n".join(lines) + (f"\n{research}" if research else "")
