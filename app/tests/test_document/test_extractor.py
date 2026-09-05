"""Unit tests for PDF and DOCX extraction functions."""

import pytest

from src.document.document import Document
from src.document.extractor import extract_docx, extract_pdf


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
