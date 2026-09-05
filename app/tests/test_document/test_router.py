"""Integration tests for the /extract endpoint using FastAPI TestClient.

`/health` is covered in tests/test_proxy/test_health.py — after the
consolidation it reports downstream service status, not a flat "ok".
"""

import io

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_extract_pdf_success(pdf_bytes: bytes) -> None:
    response = client.post(
        "/extract",
        files={"file": ("thesis.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert "text" in body
    assert "pages" in body
    assert body["format"] == "pdf"
    assert body["pages"] >= 1


def test_extract_docx_success(docx_bytes: bytes) -> None:
    response = client.post(
        "/extract",
        files={
            "file": (
                "thesis.docx",
                io.BytesIO(docx_bytes),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "text" in body
    assert body["format"] == "docx"


def test_extract_unsupported_format_returns_422() -> None:
    response = client.post(
        "/extract",
        files={"file": ("notes.txt", io.BytesIO(b"plain text"), "text/plain")},
    )
    assert response.status_code == 422


def test_extract_corrupt_pdf_returns_500() -> None:
    response = client.post(
        "/extract",
        files={"file": ("bad.pdf", io.BytesIO(b"not a real pdf"), "application/pdf")},
    )
    assert response.status_code == 500


def test_extract_detects_format_by_extension() -> None:
    """Extension-based detection works even when content-type is generic."""
    response = client.post(
        "/extract",
        files={
            "file": (
                "thesis.pdf",
                io.BytesIO(b"not a real pdf"),
                "application/octet-stream",
            )
        },
    )
    # Format is detected (pdf), but extraction fails on invalid bytes → 500 not 422
    assert response.status_code == 500
