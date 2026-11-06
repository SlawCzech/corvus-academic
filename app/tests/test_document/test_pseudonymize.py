"""Names and album numbers out of a thesis before it goes to a provider."""

import pytest

from src.document.pseudonymize import author_form, pseudonymizer_for

TITLE_PAGE = """UNIWERSYTET EKONOMICZNY W KRAKOWIE
KIERUNEK EKONOMIA
ANNA NOWAK-KOWALSKA
212345
Instytucje a wzrost gospodarczy
Praca licencjacka napisana pod kierunkiem
dr hab. Marka Wróbla, prof. UEK
Oświadczenie
Anna Nowak-Kowalska
imię i nazwisko
Spis treści
Wstęp
"""


def test_the_title_page_keeps_its_shape_and_loses_its_people() -> None:
    swap = pseudonymizer_for("Anna Nowak-Kowalska", [TITLE_PAGE])

    out = swap(TITLE_PAGE)

    assert "Nowak" not in out and "NOWAK" not in out and "Anna" not in out
    assert "Wróbl" not in out and "Marka" not in out
    assert "212345" not in out
    assert "Oświadczenie" in out and "imię i nazwisko" in out
    assert "[autor]\n[nr albumu]\nInstytucje a wzrost gospodarczy" in out
    assert "dr hab. [promotor], prof. UEK" in out


@pytest.mark.parametrize(
    "sentence",
    [
        "Rozmawiałem z Janem Kowalskim o próbie.",
        "Praca Jana Kowalskiego jest gotowa.",
        "Kowalskiemu brakuje rozdziału.",
        "Notatka: J. Kowalski oddał wstęp.",
    ],
)
def test_a_declined_name_is_still_the_name(sentence: str) -> None:
    out = pseudonymizer_for("Jan Kowalski", [])(sentence)

    assert "Kowalsk" not in out and "Jan" not in out
    assert "[autor]" in out


def test_a_fleeting_e_is_followed() -> None:
    swap = pseudonymizer_for("Marek Wróbel", [])

    assert (
        swap("Spotkanie z Markiem, praca Wróbla")
        == "Spotkanie z [autor], praca [autor]"
    )


def test_ordinary_words_in_lower_case_stay() -> None:
    swap = pseudonymizer_for("Jan Polak", [])

    assert swap("Wielu polaków uważa, że jan to miesiąc") == (
        "Wielu polaków uważa, że jan to miesiąc"
    )


def test_a_year_on_its_own_line_is_not_an_album_number() -> None:
    text = "JAN KOWALSKI\n212345\nKraków\n2026\nSpis treści\nW 2026 roku"

    out = pseudonymizer_for("Jan Kowalski", [text])(text)

    assert "2026" in out and "212345" not in out


def test_an_email_goes_too() -> None:
    swap = pseudonymizer_for("", [])

    assert swap("pisz na a.nowak@student.uek.pl") == "pisz na [email]"


def test_the_author_named_on_the_page_goes_even_if_the_card_differs() -> None:
    text = "Autor: Piotr Zieliński\nSpis treści\nZieliński pisze o..."

    out = pseudonymizer_for("Recenzja 1", [text])(text)

    assert "Zieliński" not in out


@pytest.mark.parametrize(
    ("name", "form"),
    [
        ("Anna Nowak", "Autorka"),
        ("Jan Kowalski", "Autor"),
        ("Kuba Wiśniewski", "Autor"),
        ("", "Autorka"),
    ],
)
def test_author_form(name: str, form: str) -> None:
    assert author_form(name) == form
