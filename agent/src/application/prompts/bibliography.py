"""Prompts for the bibliography check: extraction, investigation, verdicts."""

EXTRACT = (
    "You are given the bibliography of a diploma thesis. List every entry in "
    'it, in order. Return a JSON object: {"references": [{"entry": str, '
    '"authors": str, "year": int | null, "title": str, "venue": '
    "str}]}. `entry` is the whole entry exactly as written (without its "
    "number); the other fields are taken from it — `venue` is the journal, "
    "publisher or website. Do not correct, complete or add anything. Return "
    "only the raw JSON object — no markdown, no explanation."
)

INVESTIGATE = (
    "You check whether works cited in a thesis exist. For each reference "
    "below, an automatic search of Crossref and of two library catalogues "
    "found no confident match. Use the tools to look further, and pick the "
    "one that fits the kind of work: Crossref for a journal article (search "
    "again with the title alone, or with the author and a shortened title; "
    "resolve a DOI if the entry has one), the National Library of Poland for "
    "a book from a Polish publisher, Open Library for a book published "
    "elsewhere. Try a shorter or differently spelled title before giving up "
    "on an entry. You have at most {budget} tool calls in total — spend them "
    "on the entries where a search can decide something.\n\n"
    "Keep in mind what Crossref holds: most articles in international "
    "journals from about 2000 on and many English-language books. It holds "
    "few Polish monographs, textbooks, reports or theses, and it is patchy "
    "for older journal articles — the back volumes of many journals, the "
    "American Economic Review before 1999 among them, sit in JSTOR without a "
    "registered DOI. An entry of those kinds that is not found is simply not "
    "indexed. A record with the same title under another author is usually "
    "a review of the work, not the work. The library catalogues hold books: "
    "the National Library nearly everything published in Poland since the "
    "nineteenth century, Open Library much of what was published elsewhere; "
    "neither holds manuscripts, typescripts or most early prints. Two things "
    "are suspicious: an article from about 2000 on in an international "
    "journal, with volume and pages, that no search can find; and a book "
    "from an established publisher that neither catalogue knows.\n\n"
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
    'its index. Return a JSON object: {{"verdicts": [{{"index": int, '
    '"status": "found" | "mismatch" | "not_indexed" | "suspicious", '
    '"note": str, "doi": str}}]}}.\n'
    "- found: a record matches the reference (give its doi if it has one, "
    "and say in the note where it was found);\n"
    "- mismatch: the work exists but the reference gets something wrong — "
    "year, authors, title or venue (say what, give the doi);\n"
    "- not_indexed: not found, and of a kind none of the sources holds (a "
    "manuscript or typescript, an early print, a report, a thesis, a journal "
    "article from before about 2000);\n"
    "- suspicious: not found, though it claims to be of a kind a source would "
    "hold — an article from about 2000 on in an international journal, or a "
    "book from an established publisher that no catalogue knows.\n"
    "Write `note` in {language}, one sentence. Return only the raw JSON "
    "object — no markdown, no explanation."
)

LANGUAGE_NAMES = {"pl": "Polish", "en": "English"}
