"""Who judges what — the scopes of the review's analyses.

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
        "transitions between them; whether each chapter serves the stated "
        "aim; repetition, digressions and gaps in the line of argument"
    ),
    FindingSource.METHODOLOGY: (
        "the research problem, questions and hypotheses as a research design; "
        "whether the methods and data suit the aim; how the research was "
        "carried out and what limits its results; the quality, relevance and "
        "currency of the sources and how they are used in the argument"
    ),
    FindingSource.COHERENCE: (
        "whether the conclusions follow from the results the body reports, "
        "and never contradict them; whether every research question and "
        "hypothesis stated in the introduction is answered — confirmed or "
        "rejected — in the conclusions; contradictions between chapters "
        "(numbers, claims); results generalised beyond the data they rest on"
    ),
    FindingSource.REQUIREMENTS: (
        "whether each element the university requires is present and complete "
        "(abstract, introduction with the aim, conclusions, bibliography, "
        "annexes and the like); formal and editorial rules — length, citation "
        "and bibliography format, minimum number of sources, layout; any other "
        "rule the requirements document states"
    ),
}


# Every finding carries its evidence, and `verify_findings` checks it against
# the text before the review reads it: a quote the thesis does not contain is a
# finding about a thesis nobody wrote.
EVIDENCE_INSTRUCTION = (
    "\nEVIDENCE — every finding also has a `quote` field: a short passage "
    "(one sentence, at most about 200 characters) copied WORD FOR WORD from "
    "the thesis text you were given, showing the problem. Copy it exactly — "
    "do not translate, paraphrase, shorten words or fix typos; use \"...\" "
    "only to skip words inside it. When the problem is that something is "
    "absent, and there is no passage that shows it, set `quote` to \"\". "
    "A finding whose quote cannot be found in the thesis is discarded.\n"
)


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
        + EVIDENCE_INSTRUCTION
    )
