"""Reading a title page without a model: say nothing rather than guess."""

import tomllib
from pathlib import Path

import pymupdf
import pytest

from src.document.extractor import extract
from src.document.title_page import TitlePage, read_title_page

_SEED = Path(__file__).parents[2] / "scripts" / "seed_data"

_FILLED = """
UNIWERSYTET EKONOMICZNY W KATOWICACH

KIERUNEK FINANSE I RACHUNKOWOŚĆ

Jan Maria Kowalski
123456

Rola instytucji w handlu zagranicznym
The role of institutions in foreign trade

Praca licencjacka
napisana
pod kierunkiem dr. Adama Nowaka
KATOWICE 2026
Spis treści
Praca magisterska a sprawa polska
"""


def test_reads_the_university_template_once_filled_in() -> None:
    assert read_title_page(_FILLED) == TitlePage(
        author="Jan Maria Kowalski",
        field_of_study="Finanse i rachunkowość",
        thesis_type="bachelor",
        title="Rola instytucji w handlu zagranicznym",
    )


def test_a_name_in_capitals_comes_back_as_a_name() -> None:
    page = read_title_page("IZABELA NOWAK-KOWALSKA\n654321\n")

    assert page.author == "Izabela Nowak-Kowalska"


def test_the_statements_name_and_field_sit_above_their_labels() -> None:
    page = read_title_page(
        "Anna Nowak ..........\nImię i nazwisko\nZarządzanie ......\nKierunek\n"
    )

    assert page.author == "Anna Nowak"
    assert page.field_of_study == "Zarządzanie"


def test_labelled_lines_from_outside_the_template() -> None:
    page = read_title_page("Autor: Anna Nowak\nKierunek: Socjologia\nPraca magisterska")

    assert page.author == "Anna Nowak"
    assert page.field_of_study == "Socjologia"
    # Article or usual master's thesis: the title page does not say.
    assert page.thesis_type is None


def test_a_master_thesis_written_as_an_article_says_so() -> None:
    page = read_title_page("Praca magisterska\nw formie artykułu naukowego\n")

    assert page.thesis_type == "master_article"


def test_a_title_keeps_the_quotes_inside_it() -> None:
    page = read_title_page("pracy pt.: „Klub sportowy KS „Tęcza””\n")

    assert page.title == "Klub sportowy KS „Tęcza”"


@pytest.mark.parametrize(
    "template",
    [
        "zarzadzenie_117_22_zal_3_licencjat.docx",
        "zarzadzenie_117_22_zal_4_magisterska.docx",
    ],
)
def test_an_unfilled_template_gives_placeholders_to_nobody(template: str) -> None:
    data = (_SEED / "thesis_templates" / template).read_bytes()

    page = read_title_page(extract(data, template).text)

    assert page.author is None
    assert page.field_of_study is None
    assert page.title is None


def test_a_page_of_prose_suggests_nothing() -> None:
    text = "Niniejsza praca dotyczy handlu.\n" * 20

    assert read_title_page(text) == TitlePage()


def test_a_line_that_is_no_name_is_not_taken_for_one() -> None:
    assert read_title_page("Uniwersytet Ekonomiczny\n123456\n").author is None


def test_both_kinds_of_thesis_named_is_no_answer() -> None:
    page = read_title_page("Praca licencjacka\nPraca magisterska\n")

    assert page.thesis_type is None


def test_what_comes_after_the_contents_is_not_a_title_page() -> None:
    page = read_title_page("Spis treści\nAnna Nowak\n123456\n")

    assert page == TitlePage()


def test_reads_a_pdf_too() -> None:
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "KIERUNEK EKONOMIA")
    page.insert_text((72, 120), "Anna Nowak")
    page.insert_text((72, 140), "123456")
    page.insert_text((72, 200), "Praca magisterska")

    found = read_title_page(extract(pdf.tobytes(), "praca.pdf").text)

    assert found.author == "Anna Nowak"
    assert found.field_of_study == "Ekonomia"
    assert found.thesis_type is None


def test_every_demo_thesis_is_read_as_its_student() -> None:
    for folder in sorted((_SEED / "theses").iterdir()):
        student = tomllib.loads((folder / "student.toml").read_text())
        for path in folder.rglob("*.docx"):
            if "fragments" in path.parts:
                continue
            page = read_title_page(extract(path.read_bytes(), path.name).text)
            assert page.author == student["full_name"], path
            assert page.field_of_study == student["field_of_study"], path
            # A master's title page does not say article or not: no guess.
            assert page.thesis_type in (student["thesis_type"], None), path
            assert page.title == student["topic"], path
