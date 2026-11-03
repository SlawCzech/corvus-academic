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
    count_web_entries,
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


def _bibliography(*lines: str) -> str:
    return "\n".join(["Wstęp", "Tekst pracy.", "Bibliografia", *lines])


def test_web_entries_are_counted_apart_from_the_rest() -> None:
    text = _bibliography(
        "1. Kowalski, J. (2020). Finanse. Warszawa: PWN.",
        "2. NBP (2022). Komunikat. https://nbp.pl",
        "3. Bankier.pl (2023). Czy kryptowaluty zagrażają bankom?",
        "www.bankier.pl",
    )
    outline = extract_outline(text)

    assert count_bibliography_entries(text, outline) == 3
    assert count_web_entries(text, outline) == 2


def test_a_doi_link_is_not_a_web_source() -> None:
    text = _bibliography(
        "1. Smith, J. (2021). Saving. Journal of Finance. https://doi.org/10.1/x"
    )

    assert count_web_entries(text, extract_outline(text)) == 0


def test_a_netography_heading_ends_the_literature() -> None:
    """Numbered on from the literature or from 1, it stays out of the minimum."""
    for first_web_entry in ("3.", "1."):
        text = _bibliography(
            "1. Kowalski, J. (2020). Finanse. Warszawa: PWN.",
            "2. Nowak, A. (2019). Bankowość. Kraków: UEK.",
            "Netografia",
            f"{first_web_entry} NBP (2022). Komunikat. https://nbp.pl",
        )
        outline = extract_outline(text)

        assert count_bibliography_entries(text, outline) == 2
        assert count_web_entries(text, outline) == 0


def test_no_bibliography_means_no_web_count_rather_than_zero() -> None:
    text = "Wstęp\nTekst pracy."

    assert count_web_entries(text, extract_outline(text)) is None


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


# A contents block of bare section names — no dot leaders, no page numbers —
# the way a thesis typed straight into a word processor lists its chapters.
# Every "Wstęp" and "Bibliografia" in it looks exactly like a heading.
BARE_TOC_THESIS = "\n".join(
    [
        "Uniwersytet Ekonomiczny",
        "",
        "SPIS TREŚCI",
        "",
        "Wstęp",
        "Rozdział 1. Istota kryptowalut",
        "1.1. Pojęcie kryptowaluty",
        "Rozdział 2. Badanie własne",
        "2.1. Wyniki badania",
        "Zakończenie",
        "Bibliografia",
        "",
        "WSTĘP",
        "",
        "Kryptowaluty są jednym z najczęściej omawianych zjawisk. " * 20,
        "",
        "1.1. Pojęcie kryptowaluty",
        "",
        "Kryptowaluta to cyfrowy środek wymiany. " * 40,
        "",
        "2.1. Wyniki badania",
        "",
        "Badanie objęło czterdziestu respondentów. " * 40,
        "",
        "ZAKOŃCZENIE",
        "",
        "Praca pokazała wpływ kryptowalut. " * 10,
        "",
        "BIBLIOGRAFIA",
        "",
        "1. Kowalczyk, J. (2021). Kryptowaluty. Warszawa: PWN.",
        "2. Nowak, A. (2022). Blockchain w finansach. Kraków: UEK.",
    ]
)


def test_a_toc_without_page_numbers_does_not_become_the_body() -> None:
    """The contents' "Wstęp" and "Bibliografia" are not where the body runs.

    Taken as headings, they bound a 200-character "body" and take every
    numbered chapter of the real one down with them as table-of-contents lines.
    """
    outline = extract_outline(BARE_TOC_THESIS)
    titles = [s.title for s in outline]

    assert titles == [
        "SPIS TREŚCI",
        "WSTĘP",
        "1.1. Pojęcie kryptowaluty",
        "2.1. Wyniki badania",
        "ZAKOŃCZENIE",
        "BIBLIOGRAFIA",
    ]
    body = body_char_count(BARE_TOC_THESIS, outline)
    introduction = find_section(outline, "introduction")
    bibliography = find_section(outline, "bibliography")
    assert introduction is not None
    assert bibliography is not None
    assert body == bibliography.start - introduction.start
    assert count_bibliography_entries(BARE_TOC_THESIS, outline) == 2


def test_a_bare_toc_ends_at_the_first_paragraph() -> None:
    """Without a repeated heading to mark the body, prose marks it."""
    text = "\n".join(
        [
            "Spis treści",
            "Wstęp",
            "1.1. Pojęcie kryptowaluty",
            "",
            "Kryptowaluty są jednym z najczęściej omawianych zjawisk. " * 5,
            "Metodyka badań",
            "1.1. Pojęcie kryptowaluty",
            "Kryptowaluta to cyfrowy środek wymiany. " * 20,
            "Bibliografia",
            "1. Kowalczyk, J. (2021). Kryptowaluty. Warszawa: PWN.",
        ]
    )

    assert _titles(text) == [
        "Spis treści",
        "Metodyka badań",
        "1.1. Pojęcie kryptowaluty",
        "Bibliografia",
    ]


def test_table_rows_are_not_headings() -> None:
    # A DOCX table row that opens like a numbered heading: "12. Ankieta" in
    # the first cell, a count in the next.
    text = "Wstęp\nTekst.\n12. Ankieta | 30\n3.1. Wyniki szczegółowe\nTekst.\n"
    titles = [s.title for s in extract_outline(text)]
    assert "12. Ankieta | 30" not in titles
    assert "3.1. Wyniki szczegółowe" in titles


# ---------- a bachelor's thesis: "Rozdział N" and chapter summaries ----------

_CHAPTERED = """Spis treści
Wstęp
Rozdział 1. Teoretyczne podstawy zarządzania
1.1. Pojęcie zarządzania
1.2. Podsumowanie
Rozdział 2. Badania własne
2.1. Metodyka badań
Zakończenie
Literatura
Wstęp
Celem pracy jest ocena modelu zarządzania klubem sportowym w małym mieście.
Rozdział 1. Teoretyczne podstawy zarządzania
1.1. Pojęcie zarządzania
Zarządzanie to proces planowania, organizowania, motywowania i kontroli.
1.2. Podsumowanie
W rozdziale przedstawiono podstawowe pojęcia, na których opiera się praca.
Rozdział 2. Badania własne
2.1. Metodyka badań
Badanie przeprowadzono metodą wywiadu z członkami zarządu klubu.
Zakończenie
Postawiony cel został zrealizowany.
Literatura
1. Griffin, R. W. (2017). Podstawy zarządzania organizacjami. PWN.
"""


def test_a_chapters_own_summary_is_not_the_thesis_conclusions() -> None:
    """Read as the conclusions, "1.2. Podsumowanie" ended the table of contents
    at its "Zakończenie" line and took every numbered heading with it."""
    outline = extract_outline(_CHAPTERED)

    titles = [s.title for s in outline]
    assert "1.1. Pojęcie zarządzania" in titles
    summary = next(s for s in outline if s.title == "1.2. Podsumowanie")
    assert summary.canonical is None
    conclusions = [s for s in outline if s.canonical == "conclusions"]
    assert [s.title for s in conclusions] == ["Zakończenie"]


def test_a_subsection_can_still_be_the_methodology() -> None:
    outline = extract_outline(_CHAPTERED)

    method = next(s for s in outline if s.title == "2.1. Metodyka badań")
    assert method.canonical == "methodology"


def test_chapter_lines_are_headings_and_end_the_introduction() -> None:
    outline = extract_outline(_CHAPTERED)

    assert [s.title for s in outline if s.title.startswith("Rozdział")] == [
        "Rozdział 1. Teoretyczne podstawy zarządzania",
        "Rozdział 2. Badania własne",
    ]
    introduction = next(s for s in outline if s.canonical == "introduction")
    # The introduction is the introduction, not it and the chapters after it.
    assert _CHAPTERED[introduction.start :][: introduction.char_count].count("\n") == 2


def test_a_sentence_about_a_chapter_is_not_a_heading() -> None:
    text = "Wstęp\nRozdział 3 zawiera opis badań własnych.\nZakończenie\nKoniec.\n"

    assert [s.title for s in extract_outline(text)] == ["Wstęp", "Zakończenie"]


def test_contents_with_dot_leaders_end_at_the_bodys_first_heading() -> None:
    """The common PDF shape. With the entries unnamed, the body's "WSTĘP" was
    read as one more of them: no introduction, no body length, no chapters."""
    text = (
        "SPIS TREŚCI\n\n"
        "Wstęp .......... 3\n"
        "Rozdział 1. Motywacja w teorii zarządzania .......... 5\n"
        "1.1. Pojęcie motywacji .......... 7\n"
        "Zakończenie .......... 25\n"
        "Bibliografia .......... 27\n"
        "Spis wykresów .......... 29\n\n"
        "WSTĘP\n\n"
        "Na rynek pracy wchodzi pokolenie Z.\n\n"
        "ROZDZIAŁ 1. MOTYWACJA W TEORII ZARZĄDZANIA\n\n"
        "1.1. Pojęcie motywacji\n\n"
        "Motywacja to gotowość do działania.\n\n"
        "ZAKOŃCZENIE\n\nCel pracy został osiągnięty.\n\n"
        "BIBLIOGRAFIA\n\n1. Borkowska, S. (2013). Motywowanie. C.H. Beck.\n"
    )

    outline = extract_outline(text)

    assert [(s.canonical, s.title) for s in outline] == [
        ("toc", "SPIS TREŚCI"),
        ("introduction", "WSTĘP"),
        (None, "ROZDZIAŁ 1. MOTYWACJA W TEORII ZARZĄDZANIA"),
        (None, "1.1. Pojęcie motywacji"),
        ("conclusions", "ZAKOŃCZENIE"),
        ("bibliography", "BIBLIOGRAFIA"),
    ]
    assert outline_payload(text)["body_chars"] is not None
