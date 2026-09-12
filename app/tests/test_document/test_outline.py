"""Tests for the deterministic outline of an extracted thesis.

The bug these guard against: a reviewer node sees the first 30 000 characters
of a 70 000-character thesis, does not find the methodology chapter in them,
and reports it as never written. The outline is what tells it otherwise, so
it has to be right about theses as PDF extraction actually produces them —
running headings on their own line, a table of contents with dot leaders, and
a numbered bibliography that looks a lot like numbered headings.
"""

from src.document.outline import (
    body_char_count,
    count_bibliography_entries,
    extract_outline,
    find_section,
    outline_payload,
)

# Shaped like the real extraction: a table of contents naming every section,
# then the sections themselves, far enough down to fall outside any excerpt.
THESIS = "\n".join(
    [
        "Uniwersytet Ekonomiczny",
        "Spis treści",
        "Abstrakt.................................................5",
        "Wstęp....................................................6",
        "Metodyka badań..........................................18",
        "Wyniki badań............................................22",
        "Wnioski.................................................31",
        "Bibliografia:...........................................33",
        "",
        "Abstrakt",
        "Praca bada zjawisko FOMO. " * 20,
        "Wstęp",
        "Wprowadzenie do tematu. " * 40,
        "Metodyka badań",
        "Zastosowano podejście ilościowe. " * 40,
        "Wyniki badań",
        "3.1. Aktywność cyfrowa respondentów",
        "Analiza wykazała zależność. " * 40,
        "Wnioski",
        "Badanie potwierdziło hipotezę. " * 20,
        "Bibliografia:",
        "1. Adamczyk, J. (2004). Internet na usługach marketingu. Rzeszów: OW PRz.",
        "2. Bejda, G., Kułak-Bejda, A. (2022). FOMO wśród studentów. Białystok: UMB.",
        "3. Casale, S. (2025, marzec). Fear of missing out. Acta Psychologica,",
        "   104822. doi:10.1016/j.actpsy.2025.104822",
        "4.Czarnecka, M. (2026). Konsumpcjonizm wśród młodych dorosłych. Warszawa.",
        "5.",
        "Hamizar, A. i Saimima, S. (2024, kwiecień). FOMO and impulse buying.",
    ]
)


def _titles(text: str) -> list[str]:
    return [s.title for s in extract_outline(text)]


def test_running_headings_are_found_and_toc_lines_are_not() -> None:
    outline = extract_outline(THESIS)
    titles = [s.title for s in outline]

    assert "Metodyka badań" in titles
    # The table of contents names the same sections with dot leaders; counting
    # those would double every section in the map.
    assert titles.count("Metodyka badań") == 1
    assert not any("......" in t for t in titles)


def test_sections_beyond_an_excerpt_are_still_in_the_map() -> None:
    """The whole point: what the map knows, the excerpt does not have to show."""
    methodology = find_section(extract_outline(THESIS), "methodology")

    assert methodology is not None
    assert methodology.start > 1000  # well past where a short excerpt ends
    assert methodology.char_count > 0


def test_a_named_section_runs_until_the_next_named_section() -> None:
    """"Wyniki badań" followed by "3.1." is a chapter, not a 13-character stub."""
    results = find_section(extract_outline(THESIS), "results")

    assert results is not None
    assert results.char_count > 500


def test_numbered_subsections_are_kept_for_the_structure_view() -> None:
    assert "3.1. Aktywność cyfrowa respondentów" in _titles(THESIS)


def test_bibliography_entries_are_counted_not_estimated() -> None:
    outline = extract_outline(THESIS)

    # Five entries: one wraps onto a line beginning "104822." (not a sixth),
    # one omits the space after its number, and one is a bare "5." with the
    # author wrapped onto the next line. All three shapes are from real PDFs.
    assert count_bibliography_entries(THESIS, outline) == 5


def test_entry_numbering_survives_how_pdfs_break_lines() -> None:
    """"11.Czarnecka" and a bare "17." are both real; the count must survive them."""
    assert count_bibliography_entries(THESIS, extract_outline(THESIS)) == 5


def test_no_bibliography_means_no_count_rather_than_zero() -> None:
    """None says "not found"; 0 would say "found, and empty" — different bugs."""
    without = THESIS.split("Bibliografia:")[0]

    assert count_bibliography_entries(without, extract_outline(without)) is None


def test_wrapped_bibliography_entries_do_not_become_headings() -> None:
    outline = extract_outline(THESIS)
    bibliography = find_section(outline, "bibliography")

    assert bibliography is not None
    assert [s for s in outline if s.start > bibliography.start] == []


def test_body_length_excludes_what_the_length_limit_excludes() -> None:
    """A limit on the article is not a limit on the title page plus the sources.

    Measured against the extracted total, a thesis inside the limit reads as
    over it — which is a defence-blocking finding produced by arithmetic.
    """
    outline = extract_outline(THESIS)
    body = body_char_count(THESIS, outline)
    bibliography = find_section(outline, "bibliography")

    assert body is not None
    assert bibliography is not None
    assert body < len(THESIS) - bibliography.char_count + 1
    assert body > 0


def test_body_length_is_none_when_the_bounds_are_unknown() -> None:
    assert body_char_count("Tekst bez nagłówków.", []) is None


def test_payload_carries_what_the_agent_needs() -> None:
    payload = outline_payload(THESIS)

    assert payload["total_chars"] == len(THESIS)
    assert payload["bibliography_entries"] == 5
    assert isinstance(payload["body_chars"], int)
    sections = payload["sections"]
    assert isinstance(sections, list)
    assert {"title", "canonical", "start", "char_count"} <= set(sections[0])


def test_a_document_without_recognisable_headings_yields_an_empty_map() -> None:
    """Better no map than a wrong one — the nodes fall back to reading only."""
    assert extract_outline("Zwykły tekst bez nagłówków. " * 50) == []
