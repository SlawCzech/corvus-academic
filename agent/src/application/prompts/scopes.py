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


# What a finding is measured against, and how loud it may be. Without this the
# analyses had three severities and no definition of any of them, and a hosted
# model filled the gap with the standards of peer review: twenty findings on a
# sound bachelor's thesis, a "critical" for the lack of instrumental variables,
# and — since one critical finding decides the recommendation — every thesis
# sent back for revision.
CALIBRATION = (
    "\nTHE BAR — this is a diploma thesis at a regional university: a "
    "student's first independent piece of research, supervised and defended "
    "before a committee. It is not a journal article and you are not a peer "
    "reviewer. Hold it to what the university's requirements ask and to what "
    "a competent thesis at that level looks like. Do not ask for what that "
    "level does not require — a representative sample, robustness checks, "
    "advanced statistics, an exhaustive literature review, a contribution "
    "to theory. A limitation the author states openly is not a defect; a "
    "modest method honestly applied is not a defect.\n\n"
    "SEVERITY —\n"
    "- critical: the thesis cannot go to the defence as it stands. This is "
    "a closed list: (1) the work states no aim, research question or "
    "hypothesis at all; (2) the research it announces was not carried out; "
    "(3) its conclusions contradict its own results; (4) a hypothesis or "
    "question it poses is never answered. Nothing else is critical. A "
    "method that could be better, a model that is misspecified, a sample "
    "that is small or convenient, a test that is missing, a source that is "
    "weak — these are major at most, however serious they look to you. A "
    "sound thesis has no critical finding, and most weak ones have one or "
    "two.\n"
    "- major: a real weakness the supervisor would insist on fixing before "
    "the defence, though it does not undo the work: a conclusion that "
    "claims more than the results show, a chapter that does not serve the "
    "aim, a requirement of the university plainly not met. Other analyses "
    "run beside yours, each on its own scope, and a sound thesis has one "
    "or two major findings in the whole review — so in your scope it "
    "usually has none.\n"
    "- minor: worth a remark; it would not change the grade. Here belongs "
    "what a more demanding reviewer would ask for: a significance test or "
    "a measure of uncertainty that is missing, a bias the author could "
    "have controlled for, a comparison that could be better matched, "
    "literature that could be more recent, sections that could be better "
    "ordered.\n"
    "When you hesitate between two levels, choose the lower one.\n\n"
    "HOW MANY — report what a supervisor would raise in a meeting, not "
    "everything that could be said. At most five findings, the ones that "
    "matter most; fewer is better, and an empty array is the right answer "
    "for a thesis that is sound in your scope. Leave out matters of taste, "
    "other ways the work could have been done, and remarks that would apply "
    "to almost any student thesis.\n"
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
        + CALIBRATION
        + EVIDENCE_INSTRUCTION
    )
