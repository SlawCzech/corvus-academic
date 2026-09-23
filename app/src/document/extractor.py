"""Application service for extracting text from PDF and DOCX files."""

import io

import fitz  # PyMuPDF
import structlog
from docx import Document as DocxDocument

from src.document.document import Document

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


_CONTENT_TYPE_MAP: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}

_EXTENSION_MAP: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
}


def detect_format(filename: str, content_type: str = "") -> str | None:
    """Return 'pdf' or 'docx' based on file extension or content type."""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()
        if ext in _EXTENSION_MAP:
            return _EXTENSION_MAP[ext]
    return _CONTENT_TYPE_MAP.get(content_type)


# What each format's bytes start with. The name and the declared type come from
# the client; the file is now stored and handed back to a promoter, so the
# format is confirmed from the content before anything is kept.
_MAGIC: dict[str, bytes] = {
    "pdf": b"%PDF-",
    "docx": b"PK\x03\x04",
}

# The type a stored file is served back with — ours, never the client's.
CANONICAL_CONTENT_TYPE: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def detect_verified_format(data: bytes, filename: str, content_type: str = "") -> str:
    """Return the file's format once its content agrees with its name.

    Raises ValueError for an unsupported format, or for a file whose bytes are
    not what its extension or declared type claims.
    """
    fmt = detect_format(filename, content_type)
    if fmt is None:
        raise ValueError(f"Unsupported format: {filename!r} ({content_type})")
    if not data.startswith(_MAGIC[fmt]):
        raise ValueError(f"File content is not a valid {fmt.upper()}: {filename!r}")
    return fmt


def extract(data: bytes, filename: str, content_type: str = "") -> Document:
    """Extract text from an uploaded file, choosing the parser by format.

    Raises ValueError for anything that is not a PDF or a DOCX, by name or by
    content.
    """
    fmt = detect_verified_format(data, filename, content_type)
    return extract_pdf(data) if fmt == "pdf" else extract_docx(data)
