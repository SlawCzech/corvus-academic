"""Prompts for the bibliography check: extraction, investigation, verdicts."""

EXTRACT = (
    "You are given the bibliography of a diploma thesis. List every entry in "
    "it, in order. Return a JSON object: {\"references\": [{\"entry\": str, "
    "\"authors\": str, \"year\": int | null, \"title\": str, \"venue\": "
    "str}]}. `entry` is the whole entry exactly as written (without its "
    "number); the other fields are taken from it — `venue` is the journal, "
    "publisher or website. Do not correct, complete or add anything. Return "
    "only the raw JSON object — no markdown, no explanation."
)

INVESTIGATE = (
    "You check whether works cited in a thesis exist. For each reference "
    "below, an automatic Crossref search found no confident match. Use the "
    "tools to look further: search again with the title alone, or with the "
    "author and a shortened title; resolve a DOI if the entry has one. You "
    "have at most {budget} tool calls in total — spend them on the entries "
    "where a search can decide something.\n\n"
    "Keep in mind what Crossref holds: nearly every article in an "
    "international journal and many English-language books, but few Polish "
    "monographs, textbooks, reports or theses. An entry of that kind that is "
    "not found is simply not indexed. An article in an international journal, "
    "with volume and pages, that no search can find is suspicious.\n\n"
    "When you are done, say so in one sentence; your findings are collected "
    "from this conversation."
)

BUDGET_SPENT = (
    "Your tool calls are used up. Do not call a tool again — say in one "
    "sentence that you are done."
)

VERDICTS = (
    "Below is an investigation of references that an automatic check could "
    "not settle, with the tool results. Give a verdict for each reference by "
    "its index. Return a JSON object: {{\"verdicts\": [{{\"index\": int, "
    "\"status\": \"found\" | \"mismatch\" | \"not_indexed\" | \"suspicious\", "
    "\"note\": str, \"doi\": str}}]}}.\n"
    "- found: a record matches the reference (give its doi);\n"
    "- mismatch: the work exists but the reference gets something wrong — "
    "year, authors, title or venue (say what, give the doi);\n"
    "- not_indexed: not found, and of a kind Crossref rarely holds (a Polish "
    "book, a report, a thesis);\n"
    "- suspicious: not found, though it claims to be of a kind Crossref would "
    "hold — an article in an international journal.\n"
    "Write `note` in {language}, one sentence. Return only the raw JSON "
    "object — no markdown, no explanation."
)

LANGUAGE_NAMES = {"pl": "Polish", "en": "English"}
