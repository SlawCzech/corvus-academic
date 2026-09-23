"""Serving a stored file back over HTTP, and reading one in, safely."""

from urllib.parse import quote

from fastapi import HTTPException, Response, UploadFile, status

from src.shared.files import StoredFile
from src.shared.settings import settings


def attachment_response(stored: StoredFile, data: bytes) -> Response:
    """The file as a download, never rendered inline.

    Uploaded files come from outside; the browser should save them rather than
    open them in our origin, and must not second-guess the declared type.
    """
    return Response(
        content=data,
        media_type=stored.content_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(stored.filename)}"
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )


async def read_upload(file: UploadFile) -> bytes:
    """Read an upload up to the size limit; 413 beyond it.

    Reads one byte past the limit — enough to know it was exceeded without
    pulling an arbitrarily large upload into memory.
    """
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File larger than {settings.max_upload_bytes // (1024 * 1024)} MB",
        )
    return data
