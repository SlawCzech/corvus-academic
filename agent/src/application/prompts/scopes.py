"""Who judges what — the scopes of the review's three analyses.

The analyses run in parallel and never see each other's findings, so nothing
at run time can stop two of them reporting the same problem. What stops it is
this division, stated to each model: its own scope, and the two it must leave
alone. One table, rendered into all three prompts, so the boundaries cannot
drift apart prompt by prompt.
"""

from src.domain.analysis import FindingSource

SCOPES: dict[FindingSource, str] = {
    FindingSource.STRUCTURE: (
        "the order and proportions of the chapters; the logical flow and the "
        "transitions between them; whether the stated aim, the chapters and "
        "the conclusions fit together (does each chapter serve the aim, do "
        "the conclusions answer it); repetition, digressions and gaps in the "
        "line of argument"
    ),
    FindingSource.METHODOLOGY: (
        "the research problem, questions and hypotheses as a research design; "
        "whether the methods and data suit the aim; how the research was "
        "carried out and what limits its results; the quality, relevance and "
        "currency of the sources and how they are used in the argument"
    ),
    FindingSource.REQUIREMENTS: (
        "whether each element the university requires is present and complete "
        "(abstract, introduction with the aim, conclusions, bibliography, "
        "annexes and the like); formal and editorial rules — length, citation "
        "and bibliography format, minimum number of sources, layout; any other "
        "rule the requirements document states"
    ),
}


def scope_instruction(own: FindingSource) -> str:
    """The scope paragraph for one analysis: what it judges, what it leaves."""
    others = "\n".join(
        f"- {source.value}: {scope}"
        for source, scope in SCOPES.items()
        if source is not own
    )
    return (
        f"\n\nYOUR SCOPE — report only problems of this kind: {SCOPES[own]}.\n\n"
        "Other analyses of the same thesis, run separately, cover:\n"
        f"{others}\n\n"
        "Leave a problem out if it falls in their scope, however serious — "
        "it will be reported there, and reporting it twice distorts the "
        "review. Report each problem once: one finding per problem, not one "
        "per place where it shows.\n"
    )
