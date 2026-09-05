"""FastAPI router for the document extraction endpoint."""

import structlog
from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from src.document.extractor import extract_docx, extract_pdf

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()

_CONTENT_TYPE_MAP: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}

_EXTENSION_MAP: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
}


class DocumentResponse(BaseModel):
    """Response schema for a successfully extracted document."""

    text: str
    pages: int
    format: str


def _detect_format(filename: str, content_type: str) -> str | None:
    """Return 'pdf' or 'docx' based on file extension or content type."""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()
        if ext in _EXTENSION_MAP:
            return _EXTENSION_MAP[ext]
    return _CONTENT_TYPE_MAP.get(content_type)


@router.post("/extract")
async def extract(file: UploadFile) -> DocumentResponse:
    """Accept a PDF or DOCX upload and return extracted text with metadata."""
    filename = file.filename or ""
    content_type = file.content_type or ""

    fmt = _detect_format(filename, content_type)
    if fmt is None:
        logger.warning(
            "unsupported_format", filename=filename, content_type=content_type
        )
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported format: {filename!r} ({content_type})",
        )

    data = await file.read()

    try:
        doc = extract_pdf(data) if fmt == "pdf" else extract_docx(data)
    except Exception as exc:
        logger.error("extraction_failed", fmt=fmt, error=str(exc))
        raise HTTPException(
            status_code=500, detail=f"Extraction failed: {exc}"
        ) from exc

    return DocumentResponse(text=doc.text, pages=doc.pages, format=doc.format)
