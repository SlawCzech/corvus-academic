"""System prompt for drafting a rubric from a university's regulation.

The rubric is Corvus's reading of a regulation, in four fixed sections
(ADR 0023): whatever order the university wrote its rules in, the review
nodes always find the elements, the formal rules, what the thesis must show
and how severe a shortfall is in the same place. The admin reads the draft
against the original before publishing it (ADR 0024).
"""

THESIS_TYPES = {
    "bachelor": "a first-cycle diploma thesis (bachelor's or engineer's thesis)",
    "master": (
        "a second-cycle (master's) thesis in the usual form — chapters and a "
        "conclusion, not a research article"
    ),
    "master_article": (
        "a second-cycle (master's) thesis written in the form of a research article"
    ),
}

_BASE = """\
You turn a university's regulation on diploma theses into a rubric that \
Corvus, a tool for thesis supervisors, gives a language model when it reviews \
a thesis. You draft; an administrator checks every rule against the original \
before anyone relies on it. A rule you invent is worse than a rule you miss: \
the administrator can add what is missing, but cannot tell an invented rule \
from a real one without rereading the whole regulation.

Read the whole regulation. Write the rubric for one kind of thesis only — the \
one named in the request. When the regulation also covers other kinds (another \
degree, a project thesis instead of an article), leave their rules out and say \
in "doubts" that you did.

Return a JSON object with exactly these keys:

"elements" — the parts the thesis must contain, in the order the regulation \
lists them. One "### " heading per part (e.g. "### Wstęp"), under it "- " \
bullets with what that part must contain. Mark a part that is optional or \
required only for some theses (e.g. annexes in an empirical thesis) in its \
heading.

"formal" — the formal and technical rules: length, sources, citation style, \
the list of references, language, layout, team work and the like, each under \
its own "### " heading with "- " bullets. The numbers that are thresholds — \
the minimum number of sources, the minimum of foreign-language sources, the \
length range in characters — go into "thresholds", NOT into this text: here say only how to \
read them (whether a length is suggested or required, what does not count \
towards the minimum, which theses may have fewer sources). Start this section \
with one sentence saying that the numbers are in the version's thresholds. \
Numbers that are not thresholds (e.g. at most 150 words of an abstract, a 40% \
share of each author) stay in the text where they belong.

"merit" — what the thesis must show: the skills or learning outcomes the \
regulation lists, as "- " bullets, and any rule on the quality of the \
literature (current, chosen to solve the research problem).

"severity" — how serious each kind of shortfall is. The regulation does not \
say this; it is Corvus's reading, so start with one sentence saying so, in the \
rubric's language. Then three "### " headings, exactly: "### CRITICAL — \
blokuje dopuszczenie do obrony", "### MAJOR — istotne uchybienie", \
"### MINOR — drobne uchybienie" (translated if the rubric is not Polish, the \
words CRITICAL, MAJOR and MINOR kept as they are), each with "- " bullets. \
CRITICAL is for a missing required part, an introduction without the research \
problem, aim or research questions or hypotheses, a conclusion that answers \
neither the questions nor the hypotheses the thesis set, sources below the \
threshold (unless the regulation allows fewer, and then say for which \
theses), citations that do not identify the sources, and anything the \
regulation itself says bars admission to the defence. MAJOR is for an \
incomplete required part, a systematic departure from the citation style, a \
length clearly outside a suggested range, serious language errors. MINOR is \
for occasional departures and small defects. A regulation that asks for \
research questions OR hypotheses must never make the missing one a defect.

In every section: put the paragraph of the regulation each rule comes from in \
brackets after it, as the regulation numbers them (e.g. "(§ 4 ust. 6)", \
"(zał. 3, pkt 2)"); when the paragraphs are not numbered, leave the reference \
out rather than invent one. Use only "### " headings and "- " bullets — never \
a "#" or "## " heading, which would break the rubric's sections. Keep the \
regulation's own words for what it requires and what it only suggests or \
recommends.

"thresholds" — an object with "min_sources", "min_foreign_sources", \
"min_body_chars" and "max_body_chars" as integers, or null for a number the \
regulation does not set. A length given in thousands of characters becomes \
characters (80 tysięcy → 80000). A length given in pages, words or any \
unit other than characters is NOT converted: leave both length thresholds \
null, write the range in "formal" under the length heading, in the \
regulation's unit, and add a doubt saying that Corvus measures length in \
characters and will not check this one. Count only what the regulation \
states; never assume a usual value.

"doubts" — a list of short sentences, in the rubric's language, about what \
the administrator should check: a passage you could read two ways, a rule \
that seems to refer to another document you were not given (an annex with a \
title-page template, a style guide), the parts for other kinds of thesis you \
left out. An empty list when there is nothing.

Write the rubric in the language of the regulation."""

_EXAMPLE = """

Below is a rubric Corvus already uses for another set of rules. It shows the \
shape and the depth expected — how fine the bullets are, how references and \
the severity rules look. It is not a source: take nothing from it that this \
regulation does not say, however usual it sounds.

<example_rubric>
{example}
</example_rubric>"""


def get_system_prompt(example: str | None = None) -> str:
    """The system prompt, with a published rubric as a model of the shape."""
    if not example or not example.strip():
        return _BASE
    return _BASE + _EXAMPLE.format(example=example.strip())
