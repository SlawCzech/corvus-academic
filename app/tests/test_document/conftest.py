"""Shared test fixtures generating minimal PDF and DOCX files in memory."""

import io

import pytest
from docx import Document as DocxDocument
from fpdf import FPDF


@pytest.fixture
def pdf_bytes() -> bytes:
    """Generate a minimal single-page PDF for testing."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(text="Test thesis content. Chapter 1: Introduction.")  # pyright: ignore[reportCallIssue, reportUnknownMemberType]
    return bytes(pdf.output())


@pytest.fixture
def docx_bytes() -> bytes:
    """Generate a minimal DOCX document for testing."""
    doc = DocxDocument()  # pyright: ignore[reportCallIssue]
    doc.add_heading("Test Thesis", 0)  # pyright: ignore[reportUnknownMemberType]
    doc.add_paragraph("Chapter 1: Introduction")  # pyright: ignore[reportUnknownMemberType]
    doc.add_paragraph("This is a test thesis document.")  # pyright: ignore[reportUnknownMemberType]
    buf = io.BytesIO()
    doc.save(buf)  # pyright: ignore[reportUnknownMemberType]
    return buf.getvalue()
