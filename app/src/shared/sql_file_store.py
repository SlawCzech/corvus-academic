"""`FileStore` on a Postgres table — the adapter used today.

Generic over the table so each bounded context keeps its files in its own
schema (`mentoring.draft_files`, `guidelines.source_files`) and no schema is
shared across a context boundary. A context declares its table with
`FileBlobColumns` and hands the model class to `SqlFileStore`.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, LargeBinary, String, Uuid, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.files import StoredFile, sha256_hex


class FileBlobColumns:
    """The columns every file table has. Mix into a context's declarative model."""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


def _meta(row: FileBlobColumns) -> StoredFile:
    return StoredFile(
        id=row.id,
        filename=row.filename,
        content_type=row.content_type,
        size=row.size,
        sha256=row.sha256,
    )


class SqlFileStore[M: FileBlobColumns]:
    """Files as rows of one table. Flushes, never commits — see `FileStore`."""

    def __init__(self, session: AsyncSession, model: type[M]) -> None:
        self._session = session
        self._model = model

    async def put(self, filename: str, content_type: str, data: bytes) -> StoredFile:
        row = self._model()
        row.id = uuid.uuid4()
        row.filename = filename
        row.content_type = content_type
        row.size = len(data)
        row.sha256 = sha256_hex(data)
        row.data = data
        row.created_at = datetime.now(UTC)
        self._session.add(row)
        await self._session.flush()
        return _meta(row)

    async def get(self, file_id: uuid.UUID) -> tuple[StoredFile, bytes] | None:
        row = await self._session.get(self._model, file_id)
        if row is None:
            return None
        return _meta(row), row.data

    async def delete(self, file_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(self._model).where(self._model.id == file_id)
        )
