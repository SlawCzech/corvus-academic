"""What a title page says about a thesis, read without a model.

A suggestion for a form the promoter checks, so it says nothing rather than
guess. It knows the university's template (Zarządzenie 117/22, zał. 3 and 4):
the author's name above their album number and in the statement, and "KIERUNEK
…" at the top. An unfilled template carries placeholders, and those are not
answers.
"""

import re
from dataclasses import dataclass

# The front matter ends at the table of contents. The cap is for a thesis
# without one: past it, a line is more likely prose than a title page.
_FRONT_CHARS = 8000
_CONTENTS = re.compile(r"^spis\s+treści\b", re.IGNORECASE)

_FIELD_INLINE = re.compile(r"^kierunek(?:\s+studiów)?\s*[:\s]\s*(\S.*)$", re.IGNORECASE)
_AUTHOR_INLINE = re.compile(
    r"^(?:autor(?:ka)?|imię\s+i\s+nazwisko)\s*:\s*(\S.*)$", re.IGNORECASE
)
_ALBUM = re.compile(r"^(?:(?:nr|numer)\s+albumu\s*:?\s*)?\d{4,7}\b", re.IGNORECASE)
_WORD = r"[^\W\d_]+(?:[-'’][^\W\d_]+)?"
_NAME = re.compile(rf"^{_WORD}(?: {_WORD}){{1,3}}$")
# To the last quote on the line: a title may hold quotes of its own.
_QUOTED_TITLE = re.compile(r"pt\.?\s*:?\s*[„\"“](.+)[”\"]")
_BACHELOR = re.compile(r"^praca\s+(?:licencjacka|inżynierska)\b", re.IGNORECASE)
_MASTER = re.compile(r"^praca\s+magisterska\b", re.IGNORECASE)
# A master's thesis written as a research article says so on its title page.
_ARTICLE = re.compile(r"\bartyku[łl]", re.IGNORECASE)
_TITLE_PLACEHOLDER = re.compile(r"^tytuł\s+pracy\b", re.IGNORECASE)
_AUTHOR_PLACEHOLDER = "imię i nazwisko autora"
_NOT_A_NAME = re.compile(r"\b(?:uniwersytet|praca|kierunek|wydział)\b", re.IGNORECASE)
_TRAILING_DOTS = re.compile(r"[\s.…_]+$")


@dataclass(frozen=True)
class TitlePage:
    """What was found; None for anything that was not there to read."""

    author: str | None = None
    field_of_study: str | None = None
    thesis_type: str | None = None
    title: str | None = None


def front_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text[:_FRONT_CHARS].splitlines():
        line = raw.strip()
        if _CONTENTS.match(line):
            break
        if line:
            lines.append(line)
    return lines


def _unshout(value: str) -> str:
    """A title page sets names in capitals; a form should not."""
    return value.capitalize() if value.isupper() else value


def _name(value: str) -> str | None:
    """The value as a person's name, or None when it does not look like one."""
    candidate = " ".join(_TRAILING_DOTS.sub("", value).split())
    if not _NAME.match(candidate) or _NOT_A_NAME.search(candidate):
        return None
    if candidate.lower() == _AUTHOR_PLACEHOLDER:
        return None
    return candidate.title() if candidate.isupper() else candidate


def _line_above(lines: list[str], label: str) -> str | None:
    """The line over a form label: the statements put the value there."""
    for index, line in enumerate(lines):
        if index > 0 and line.lower() == label:
            return lines[index - 1]
    return None


def _author(lines: list[str]) -> str | None:
    above = _line_above(lines, "imię i nazwisko")
    candidates = [above] if above else []
    candidates += [
        match.group(1) for line in lines if (match := _AUTHOR_INLINE.match(line))
    ]
    candidates += [
        lines[index - 1]
        for index, line in enumerate(lines)
        if index > 0 and _ALBUM.match(line)
    ]
    return next((name for c in candidates if (name := _name(c))), None)


def _field(value: str) -> str | None:
    cleaned = _TRAILING_DOTS.sub("", value).strip()
    return _unshout(cleaned) if cleaned and "(" not in cleaned else None


def _field_of_study(lines: list[str]) -> str | None:
    candidates = [
        match.group(1) for line in lines if (match := _FIELD_INLINE.match(line))
    ]
    above = _line_above(lines, "kierunek")
    if above:
        candidates.append(above)
    return next((field for c in candidates if (field := _field(c))), None)


def _thesis_type(lines: list[str]) -> str | None:
    bachelor = any(_BACHELOR.match(line) for line in lines)
    master = any(_MASTER.match(line) for line in lines)
    if bachelor == master:
        return None
    if bachelor:
        return "bachelor"
    # "Praca magisterska" alone does not say which: a Katowice article and a
    # usual master's thesis share the words. The promoter picks.
    if any(_ARTICLE.search(line) for line in lines):
        return "master_article"
    return None


def _title(front: str, lines: list[str]) -> str | None:
    """The title the statement quotes, else the line under the album number."""
    quoted = _QUOTED_TITLE.search(front)
    if quoted:
        return " ".join(quoted.group(1).split())
    for index, line in enumerate(lines[:-1]):
        following = lines[index + 1]
        if _ALBUM.match(line) and not _TITLE_PLACEHOLDER.match(following):
            return _unshout(following)
    return None


def read_title_page(text: str) -> TitlePage:
    """Read the title page at the start of an extracted thesis."""
    lines = front_lines(text)
    return TitlePage(
        author=_author(lines),
        field_of_study=_field_of_study(lines),
        thesis_type=_thesis_type(lines),
        title=_title("\n".join(lines), lines),
    )
