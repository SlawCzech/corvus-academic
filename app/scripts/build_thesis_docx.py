# /// script
# requires-python = ">=3.12"
# dependencies = ["python-docx>=1.1"]
# ///
"""Build a demo thesis DOCX from Markdown on top of the university template.

The template (Zarządzenie 117/22, zał. 3 or 4) contributes the title page, the
supervisor's and the author's statements and the page setup; everything after
"Spis treści" is replaced with the thesis body, formatted as the template's own
instructions prescribe (Arial, 16/14/12 pt headings, 1.5 line spacing…).

    uv run scripts/build_thesis_docx.py scripts/seed_data/theses/03_kiepski

The Markdown is a small subset: a `key: value` front matter, `#`/`##`/`###`
headings, paragraphs, `- ` lists, pipe tables, *italic* and **bold**.
Paragraphs starting with "Tabela"/"Rys." are captions, with "Źródło:" sources.
Under the "Literatura" heading, paragraphs are bibliography entries.
"""

import re
import sys
from pathlib import Path

from docx import Document
from docx.document import Document as DocumentObject
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.table import Table
from docx.text.paragraph import Paragraph

_TEMPLATES = Path(__file__).parent / "seed_data" / "thesis_templates"
_TEMPLATE = {
    "bachelor": _TEMPLATES / "zarzadzenie_117_22_zal_3_licencjat.docx",
    "master_article": _TEMPLATES / "zarzadzenie_117_22_zal_4_magisterska.docx",
}
_FONT = "Arial"
_HEADINGS = {1: (16, 18), 2: (14, 12), 3: (12, 6)}  # level: (size pt, space pt)
_INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*)")


def parse(source: str) -> tuple[dict[str, str], list[str]]:
    meta: dict[str, str] = {}
    lines = source.splitlines()
    if lines and lines[0] == "---":
        end = lines.index("---", 1)
        for line in lines[1:end]:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"')
        lines = lines[end + 1 :]
    return meta, lines


def set_text(paragraph: Paragraph, text: str) -> None:
    """Replace a paragraph's text, keeping its first run's formatting.

    Everything else goes, content controls (`w:sdt`) included — the template
    hides placeholder text in them, out of reach of `paragraph.runs`.
    """
    p = paragraph._p  # pyright: ignore[reportPrivateUsage]
    first = next(p.iter(qn("w:r")))
    for child in list(p):
        if child.tag != qn("w:pPr"):
            p.remove(child)
    p.append(first)
    paragraph.runs[0].text = text


def clear_headers(doc: DocumentObject) -> None:
    """Drop the template's "Załącznik N. Szablon…" running header."""
    for section in doc.sections:
        for header in (section.header, section.first_page_header):
            if header.is_linked_to_previous:
                continue
            for p in header.paragraphs:
                for run in p.runs:
                    run.text = ""


def fill_front_matter(doc: DocumentObject, meta: dict[str, str]) -> None:
    paragraphs = doc.paragraphs
    for i, p in enumerate(paragraphs):
        text = p.text.strip()
        if text.startswith("KIERUNEK ("):
            set_text(p, f"KIERUNEK {meta['field'].upper()}")
        elif text == "IMIĘ I NAZWISKO AUTORA":
            set_text(p, meta["author"])
        elif text.startswith("123456"):
            set_text(p, meta["album"])
        elif text == "TYTUŁ PRACY DYPLOMOWEJ W JĘZYKU ANGIELSKIM":
            set_text(p, meta["title_en"])
        elif text == "TYTUŁ PRACY DYPLOMOWEJ":
            set_text(p, meta["title"])
        elif text.startswith("Praca licencjacka/"):
            set_text(p, "Praca licencjacka")
        elif text.startswith("pod kierunkiem ("):
            set_text(p, f"pod kierunkiem {meta['supervisor']}")
        elif text.startswith("KATOWICE"):
            set_text(p, f"KATOWICE {meta['year']}")
        elif text in ("Imię i nazwisko", "Kierunek", "Nr albumu"):
            value = {
                "Imię i nazwisko": meta["author"],
                "Kierunek": meta["field"],
                "Nr albumu": meta["album"],
            }[text]
            previous = paragraphs[i - 1]
            set_text(previous, re.sub(r"^[.…]+", value, previous.text))
        elif "pt.:" in text and text.startswith("Mając świadomość"):
            head = p.text.split("pt.:")[0]
            if meta["level"] == "bachelor":
                head = head.replace("licencjacka/inżynierska", "licencjacka")
            set_text(p, f"{head}pt.: „{meta['title']}”")
            follower = paragraphs[i + 1]
            if not follower.text.strip(" .…"):
                follower._p.getparent().remove(follower._p)  # pyright: ignore[reportPrivateUsage]


def truncate_after_toc(doc: DocumentObject) -> Paragraph:
    """Drop the template's sample body; return the "Spis treści" paragraph."""
    toc = next(p for p in doc.paragraphs if p.text.strip() == "Spis treści")
    body = doc.element.body
    after = False
    for child in list(body):
        if child is toc._p:  # pyright: ignore[reportPrivateUsage]
            after = True
        elif after and child.tag != qn("w:sectPr"):
            body.remove(child)
    return toc


def add_runs(paragraph: Paragraph, text: str, size: int) -> None:
    for chunk in _INLINE.split(text):
        if not chunk:
            continue
        bold = chunk.startswith("**")
        italic = not bold and chunk.startswith("*")
        run = paragraph.add_run(chunk.strip("*") if bold or italic else chunk)
        run.bold = bold or None
        run.italic = italic or None
        run.font.name = _FONT
        run.font.size = Pt(size)
        run.font.color.rgb = RGBColor(0, 0, 0)


def body_paragraph(doc: DocumentObject, text: str) -> Paragraph:
    p = doc.add_paragraph(style="Normal")
    fmt = p.paragraph_format
    fmt.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    fmt.first_line_indent = Cm(1)
    fmt.line_spacing = 1.5
    fmt.space_before = fmt.space_after = Pt(0)
    add_runs(p, text, 12)
    return p


def plain_paragraph(
    doc: DocumentObject, text: str, size: int, *, hanging: bool = False
) -> Paragraph:
    p = doc.add_paragraph(style="Normal")
    fmt = p.paragraph_format
    fmt.first_line_indent = Cm(-1) if hanging else Cm(0)
    fmt.left_indent = Cm(1) if hanging else Cm(0)
    fmt.line_spacing = 1.0
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(6)
    add_runs(p, text, size)
    return p


def heading(doc: DocumentObject, text: str, level: int, *, new_page: bool) -> None:
    size, space = _HEADINGS[level]
    p = doc.add_paragraph(style=f"Heading {level}")
    fmt = p.paragraph_format
    fmt.alignment = WD_ALIGN_PARAGRAPH.LEFT
    fmt.first_line_indent = Cm(0)
    fmt.line_spacing = 1.0
    fmt.space_before = fmt.space_after = Pt(space)
    fmt.page_break_before = new_page
    fmt.keep_with_next = True
    add_runs(p, f"**{text}**", size)


def table(doc: DocumentObject, rows: list[list[str]]) -> None:
    t: Table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.alignment = 1  # centre
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")
        borders.append(element)
    t._tbl.tblPr.append(borders)  # pyright: ignore[reportPrivateUsage]
    for r, cells in enumerate(rows):
        for c, value in enumerate(cells):
            p = t.cell(r, c).paragraphs[0]
            p.paragraph_format.first_line_indent = Cm(0)
            add_runs(p, f"**{value}**" if r == 0 else value, 10)


def toc_field(anchor: Paragraph, entries: list[tuple[int, str]]) -> None:
    """A real TOC field with its entries cached, so text extractors see them.

    Word fills in page numbers when it updates fields on open.
    """
    last = anchor
    for i, (level, text) in enumerate(entries):
        p = last.insert_paragraph_before("")  # placeholder, moved below
        last._p.addnext(p._p)  # pyright: ignore[reportPrivateUsage]
        p.paragraph_format.left_indent = Cm(0.6 * (level - 1))
        p.paragraph_format.first_line_indent = Cm(0)
        if i == 0:
            for kind, instr in (
                ("begin", None),
                (None, r'TOC \o "1-3" \h \z \u'),
                ("separate", None),
            ):
                run = p.add_run()
                if kind:
                    char = OxmlElement("w:fldChar")
                    char.set(qn("w:fldCharType"), kind)
                    run._r.append(char)  # pyright: ignore[reportPrivateUsage]
                else:
                    code = OxmlElement("w:instrText")
                    code.set(qn("xml:space"), "preserve")
                    code.text = instr
                    run._r.append(code)  # pyright: ignore[reportPrivateUsage]
        add_runs(p, text, 12)
        last = p
    end = last.add_run()
    char = OxmlElement("w:fldChar")
    char.set(qn("w:fldCharType"), "end")
    end._r.append(char)  # pyright: ignore[reportPrivateUsage]


def build(directory: Path) -> Path:
    meta, lines = parse((directory / "thesis.md").read_text(encoding="utf-8"))
    doc = Document(str(_TEMPLATE[meta["level"]]))
    fill_front_matter(doc, meta)
    clear_headers(doc)
    toc = truncate_after_toc(doc)

    entries: list[tuple[int, str]] = []
    in_bibliography = False
    paragraph: list[str] = []
    rows: list[list[str]] = []

    def flush() -> None:
        nonlocal paragraph, rows
        if rows:
            table(doc, [r for r in rows if not set("".join(r)) <= set("-: ")])
            rows = []
        if not paragraph:
            return
        text = " ".join(paragraph)
        paragraph = []
        if text.startswith(("Tabela ", "Rys. ")):
            plain_paragraph(doc, text, 11)
        elif text.startswith("Źródło:"):
            plain_paragraph(doc, text, 10)
        elif in_bibliography:
            plain_paragraph(doc, text, 12, hanging=True)
        else:
            body_paragraph(doc, text)

    for line in lines:
        stripped = line.strip()
        if match := re.match(r"^(#{1,3}) (.+)$", stripped):
            flush()
            level, text = len(match[1]), match[2]
            heading(doc, text, level, new_page=level == 1)
            entries.append((level, text))
            if level == 1:
                in_bibliography = text == "Literatura"
        elif stripped.startswith("|"):
            if paragraph:
                flush()
            rows.append([c.strip() for c in stripped.strip("|").split("|")])
        elif stripped.startswith("- "):
            flush()
            p = body_paragraph(doc, f"– {stripped[2:]}")
            p.paragraph_format.first_line_indent = Cm(-0.5)
            p.paragraph_format.left_indent = Cm(1.5)
        elif not stripped:
            flush()
        else:
            if rows:
                flush()
            paragraph.append(stripped)
    flush()

    toc_field(toc, entries)
    update = OxmlElement("w:updateFields")
    update.set(qn("w:val"), "true")
    doc.settings.element.append(update)

    out = directory / meta["output"]
    doc.save(str(out))
    return out


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print(build(Path(arg)))
