"""Who wrote and supervised a thesis, taken out before its text leaves Corvus.

A provider needs the work, not the people: the author's name and album number
and the promoter's name are swapped for markers wherever they appear, and the
title page and the statement keep their shape, so a check for a title page
still finds one (ADR 0023). No model: names are matched in code.

Polish declines names, so a name is matched by its stem with a short ending
(Kowalski, Kowalskiego, Kowalską; Marek, Marka). A match must start with a
capital letter, which keeps ordinary words out. It over-redacts rather than
leaks: a cited author who shares the student's surname becomes a marker too.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from src.document.title_page import front_lines, read_title_page

AUTHOR = "[autor]"
PROMOTER = "[promotor]"
ALBUM = "[nr albumu]"
EMAIL = "[email]"

_VOWELS = "aeiouyąęó"
_ENDING = r"[^\W\d_]{0,4}"
# A first name ending in -a is a woman's, except these.
_MALE_IN_A = {"kuba", "barnaba", "bonawentura", "kosma", "jarema", "dyzma"}

_ALBUM_LINE = re.compile(
    r"(?:nr|numer)\s+albumu\s*:?\s*(\d{4,7})\b|^(\d{5,7})$", re.IGNORECASE
)
_SUPERVISOR = re.compile(
    r"(?:promotor(?:ka)?|opiekun(?:ka)?(?:\s+naukow\w*)?|pod\s+kierunkiem)\s*:?\s*(.*)$",
    re.IGNORECASE,
)
_TITLE_WORDS = {
    "dr",
    "dra",
    "hab",
    "prof",
    "profesor",
    "profesora",
    "inż",
    "mgr",
    "doktor",
    "doktora",
    "uczelni",
    "uniwersytetu",
    "katedra",
    "katedry",
    "instytut",
    "instytutu",
    "zakład",
    "zakładu",
    "wydział",
    "wydziału",
}
_NAME_WORD = re.compile(r"[^\W\d_]+")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _stems(token: str) -> set[str]:
    """What a declined form of this name starts with."""
    lower = token.lower()
    stems = {lower}
    if len(lower) >= 3 and lower[-1] in _VOWELS:
        stems.add(lower[:-1])
    # A fleeting e: Marek → Marka, Wróbel → Wróbla, Paweł → Pawła.
    if len(lower) >= 4 and lower[-2] == "e" and lower[-1] not in _VOWELS:
        stems.add(lower[:-2] + lower[-1])
    return stems


def _name_tokens(name: str) -> list[str]:
    return [t for t in _NAME_WORD.findall(name) if len(t) >= 3]


def _pattern(tokens: Iterable[str]) -> re.Pattern[str] | None:
    stems = sorted({s for t in tokens for s in _stems(t)}, key=len, reverse=True)
    if not stems:
        return None
    alternatives = "|".join(re.escape(s) for s in stems)
    return re.compile(rf"\b(?:{alternatives}){_ENDING}\b", re.IGNORECASE)


def _swap(text: str, pattern: re.Pattern[str] | None, marker: str) -> str:
    if pattern is None:
        return text

    def replace(match: re.Match[str]) -> str:
        # A name is capitalised; the same letters in lower case are a word.
        return marker if match.group(0)[0].isupper() else match.group(0)

    swapped = pattern.sub(replace, text)
    # "Jan Kowalski" becomes one marker, not two.
    return re.sub(
        rf"{re.escape(marker)}(?:[ \t]+{re.escape(marker)})+", marker, swapped
    )


def _supervisor_names(lines: list[str]) -> list[str]:
    """The promoter's name as the title page gives it, without degrees."""
    names: list[str] = []
    for index, line in enumerate(lines):
        match = _SUPERVISOR.search(line)
        if not match:
            continue
        value = match.group(1).strip() or (
            lines[index + 1] if index + 1 < len(lines) else ""
        )
        if value.isupper():
            value = value.title()
        names += [
            word
            for word in _name_tokens(value)
            if word[0].isupper()
            and not word.isupper()
            and word.lower() not in _TITLE_WORDS
        ]
    return names


def _album_numbers(lines: list[str]) -> set[str]:
    numbers: set[str] = set()
    for line in lines:
        match = _ALBUM_LINE.search(line)
        if match:
            numbers.add(match.group(1) or match.group(2))
    return numbers


@dataclass(frozen=True)
class Pseudonymizer:
    """Swaps the people of one thesis for markers, in any text about it."""

    author: re.Pattern[str] | None
    promoter: re.Pattern[str] | None
    albums: frozenset[str]

    def __call__(self, text: str) -> str:
        text = _swap(text, self.author, AUTHOR)
        text = _swap(text, self.promoter, PROMOTER)
        for number in self.albums:
            text = re.sub(rf"\b{re.escape(number)}\b", ALBUM, text)
        return _EMAIL.sub(EMAIL, text)


def pseudonymizer_for(student_name: str, theses: Iterable[str]) -> Pseudonymizer:
    """A pseudonymizer for a student and the texts of their thesis.

    The name on the student's card is taken whole; each thesis adds the author
    its title page names (a one-off review's card may say something else), the
    promoter and the album number.
    """
    author = _name_tokens(student_name)
    promoter: list[str] = []
    albums: set[str] = set()
    for text in theses:
        lines = front_lines(text)
        found = read_title_page(text).author
        if found:
            author += _name_tokens(found)
        promoter += _supervisor_names(lines)
        albums |= _album_numbers(lines)
    # The author's name never stands for the promoter, even if a page says so.
    promoter = [p for p in promoter if p.lower() not in {a.lower() for a in author}]
    return Pseudonymizer(_pattern(author), _pattern(promoter), frozenset(albums))


def author_form(name: str) -> str:
    """How a review refers to the author: "Autorka" or "Autor", from a first name.

    A guess for Polish names, defaulting to "Autorka" as the review prompt did
    when the name was still in it.
    """
    tokens = _name_tokens(name)
    if not tokens:
        return "Autorka"
    first = tokens[0].lower()
    return "Autorka" if first.endswith("a") and first not in _MALE_IN_A else "Autor"
