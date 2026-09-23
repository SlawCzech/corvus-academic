"""Storing uploaded files — the port every bounded context depends on.

What a context needs from file storage is small: put bytes, get them back,
forget them. Keeping it to this protocol is what lets the Postgres adapter
(`sql_file_store.py`) be swapped for object storage later without a context
noticing.
"""

import hashlib
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class StoredFile:
    """What is known about a stored file, without its bytes."""

    id: UUID
    filename: str
    content_type: str
    size: int
    sha256: str


def sha256_hex(data: bytes) -> str:
    """The fingerprint stored with every file, and kept after it is deleted."""
    return hashlib.sha256(data).hexdigest()


class FileStore(Protocol):
    """Put, get and delete files.

    Implementations never commit: a file is written in the same unit of work
    as the row that points at it, so the two can never disagree.
    """

    async def put(self, filename: str, content_type: str, data: bytes) -> StoredFile:
        """Store the bytes and return what was stored."""
        ...

    async def get(self, file_id: UUID) -> tuple[StoredFile, bytes] | None:
        """Return the file and its bytes, or None if there is no such file."""
        ...

    async def delete(self, file_id: UUID) -> None:
        """Remove the file; a missing file is not an error."""
        ...
