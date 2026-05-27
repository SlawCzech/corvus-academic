"""Application service for extracting text from PDF and DOCX files."""

import io

import fitz  # PyMuPDF
import structlog
from docx import Document as DocxDocument

from src.domain.document import Document

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def extract_pdf(file: bytes) -> Document:
    """Extract text and page count from a PDF file."""
    pdf = fitz.open(stream=file, filetype="pdf")  # pyright: ignore[reportUnknownMemberType]
    pages = len(pdf)
    if pages == 0:
        raise ValueError("PDF has no pages or could not be parsed")
    parts: list[str] = []
    for page in pdf:
        raw = page.get_text()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        # get_text() returns str by default; cast defensively for strict mode
        parts.append(str(raw))  # pyright: ignore[reportUnknownArgumentType]
    pdf.close()
    text = "".join(parts)
    logger.info("pdf_extracted", pages=pages, chars=len(text))
    return Document(text=text, pages=pages, format="pdf")


def extract_docx(file: bytes) -> Document:
    """Extract text and section count from a DOCX file."""
    docx = DocxDocument(io.BytesIO(file))  # pyright: ignore[reportUnknownMemberType]
    paragraphs: list[str] = []
    for para in docx.paragraphs:  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        raw: str = para.text  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        paragraphs.append(raw)
    text = "\n".join(paragraphs)
    sections: list[object] = list(docx.sections)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportUnknownVariableType]
    pages = len(sections)
    logger.info("docx_extracted", sections=pages, chars=len(text))
    return Document(text=text, pages=pages, format="docx")
