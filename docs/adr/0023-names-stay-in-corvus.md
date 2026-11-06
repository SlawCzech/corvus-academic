# ADR 0023: Names stay in Corvus

- Status: Accepted
- Date: 2026-11-06
- Amends: [ADR 0022](0022-every-action-runs-on-a-providers-key.md) (what a provider receives)

## Context

Since ADR 0022 every action runs on a cloud provider, and the actions that read a thesis send its whole extracted text. That text starts with the title page and the statement of authorship: the author's name, the album number, the promoter's name, sometimes an email. A review also sent `metadata.author`, the name on the student's card, which the review node used only to choose between "Autor" and "Autorka". Meeting notes and the promoter's detail carry the student's name too.

None of it helps the analysis. Cutting the front matter out is not the answer either: the requirements node checks that the title page and the statement exist, and their absence is a critical finding.

## Decision

- **`app` swaps the people for markers before a context leaves.** `ActionService.trigger` passes every assembled context through `pseudonymize_context`: the author becomes `[autor]`, the promoter `[promotor]`, the album number `[nr albumu]`, any email `[email]`. Every string goes through it, notes and detail included, except the guideline rubric and thresholds. The title page and the statement keep their shape, so the structure checks still see them.
- **Code finds the names, not a model** (`document/pseudonymize.py`). The author comes from the student's card and from the title page (a one-off review's card may say something else), the promoter from a "Promotor" / "pod kierunkiem" line on the title page, the album number from the front matter. Users have no names in `identity`, so the title page is the only source for the promoter.
- **Declension is matched by stem.** A name matches its stem plus up to four letters, with a fleeting e followed (Marek → Marka), and only where it starts with a capital letter.
- **The document map is drawn again** over the pseudonymized text, because its offsets are into the text and a marker is not as long as the name.
- **The review gets `metadata.author_form`, not the name**: "Autorka" for a first name ending in -a (bar a few men's names), else "Autor".

## Consequences

- A cited author who shares the student's surname becomes `[autor]` too. Over-redaction is the price of matching declined forms without a model. Bibliography verification may then fail to match that one entry.
- Not covered: nicknames in notes ("Kasia" for Katarzyna), names of other people in the text (respondents, interviewees), and the promoter's name when the title page does not give it. The thesis itself still goes to the provider; this takes out who wrote it, not what it says.
- Results can contain the markers (a meeting note draft saying "[autor]"); the promoter edits them before accepting.
- Deploy order does not matter: the agent falls back to "Autorka" when `author_form` is missing, and an older agent ignores it.

## Amendment (2026-11-06): the bibliography check and the markers

A self-citation reached `verify_bibliography` as `[autor], J. P. (2025). O wyższości folwarku… [maszynopis w posiadaniu autora]` and came back confirmed, with the DOI of an author-less Crossref chapter titled "Autor o Autora": both its title words occur in the entry, and a record without authors passed the author check by default.

- **An entry whose first author is a marker is not looked up.** No source can confirm an author whose name never left Corvus, and an author-less record with a fitting title would pass for the work. It is marked "Niesprawdzona" with a note saying why, without going to Crossref, the catalogues or the agent. A marker later in the author list changes nothing: the first author is the one compared. Sending the entry would leak nothing (it holds only the marker), so this is about the verdict, not privacy.
- **A title must match both ways.** When the extraction gives the reference's title, the record's title must also cover at least half of its main title (no subtitle), not just have its own words somewhere in the entry. This holds for every entry, not only for marked ones.
- **The result shows the marker, not the name.** As with the other results, `app` does not keep the mapping after it sends the context, and the entry is shown as the provider received it. The promoter knows whose work `[autor]` is; restoring it would mean pseudonymizing the thesis again at read time for one label.
