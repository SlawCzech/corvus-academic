"""Unit tests for PDF and DOCX extraction functions."""

import io

import pytest
from docx import Document as DocxDocument

from src.document.document import Document
from src.document.extractor import detect_verified_format, extract_docx, extract_pdf


def test_extract_pdf_returns_document(pdf_bytes: bytes) -> None:
    doc = extract_pdf(pdf_bytes)
    assert isinstance(doc, Document)


def test_extract_pdf_format(pdf_bytes: bytes) -> None:
    doc = extract_pdf(pdf_bytes)
    assert doc.format == "pdf"


def test_extract_pdf_has_pages(pdf_bytes: bytes) -> None:
    doc = extract_pdf(pdf_bytes)
    assert doc.pages >= 1


def test_extract_pdf_contains_text(pdf_bytes: bytes) -> None:
    doc = extract_pdf(pdf_bytes)
    assert "Introduction" in doc.text


def test_extract_pdf_invalid_raises() -> None:
    with pytest.raises((ValueError, Exception)):
        extract_pdf(b"not a real pdf file")


def test_extract_docx_returns_document(docx_bytes: bytes) -> None:
    doc = extract_docx(docx_bytes)
    assert isinstance(doc, Document)


def test_extract_docx_format(docx_bytes: bytes) -> None:
    doc = extract_docx(docx_bytes)
    assert doc.format == "docx"


def test_extract_docx_contains_text(docx_bytes: bytes) -> None:
    doc = extract_docx(docx_bytes)
    assert "Introduction" in doc.text


def _docx_with_table() -> bytes:
    doc = DocxDocument()
    doc.add_paragraph("Tabela 1 przedstawia stopę bezrobocia.")
    table = doc.add_table(rows=3, cols=2)
    for row, values in zip(
        table.rows,
        [("Rok", "Stopa (%)"), ("2004", "19,0"), ("2008", "9,5")],
        strict=True,
    ):
        for cell, value in zip(row.cells, values, strict=True):
            cell.text = value
    doc.add_paragraph("Źródło: GUS.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_extract_docx_keeps_tables_in_document_order() -> None:
    lines = extract_docx(_docx_with_table()).text.splitlines()
    assert lines == [
        "Tabela 1 przedstawia stopę bezrobocia.",
        "Rok | Stopa (%)",
        "2004 | 19,0",
        "2008 | 9,5",
        "Źródło: GUS.",
    ]


def test_extract_docx_takes_a_merged_cell_once() -> None:
    doc = DocxDocument()
    table = doc.add_table(rows=2, cols=3)
    table.cell(0, 0).merge(table.cell(0, 1)).text = "Wiek"
    table.cell(0, 2).text = "N"
    for cell, value in zip(table.rows[1].cells, ("20–29", "30–39", "4"), strict=True):
        cell.text = value
    buf = io.BytesIO()
    doc.save(buf)
    lines = extract_docx(buf.getvalue()).text.splitlines()
    assert lines[-2:] == ["Wiek | N", "20–29 | 30–39 | 4"]


def test_verified_format_accepts_matching_content(
    pdf_bytes: bytes, docx_bytes: bytes
) -> None:
    assert detect_verified_format(pdf_bytes, "praca.pdf") == "pdf"
    assert detect_verified_format(docx_bytes, "praca.docx") == "docx"


def test_verified_format_rejects_content_that_contradicts_the_name(
    docx_bytes: bytes,
) -> None:
    with pytest.raises(ValueError, match="not a valid PDF"):
        detect_verified_format(docx_bytes, "praca.pdf")


def test_verified_format_rejects_unsupported_names() -> None:
    with pytest.raises(ValueError, match="Unsupported format"):
        detect_verified_format(b"%PDF-", "praca.txt")
