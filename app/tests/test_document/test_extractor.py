"""Unit tests for PDF and DOCX extraction functions."""

import pytest

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
