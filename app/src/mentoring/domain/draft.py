"""Domain entity for an uploaded version of a student's thesis."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

# What a promoter sees in a list of versions, instead of the whole text.
_PREVIEW_CHARS = 400


@dataclass
class ThesisDraft:
    """One uploaded version of the thesis, with its extracted text.

    Versions are numbered per student and never reused: the history of what
    the student handed in is exactly what `check_progress` compares.
    """

    id: UUID
    student_id: UUID
    version_number: int
    filename: str
    text: str
    pages: int
    format: str
    uploaded_by: UUID
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # The original upload. `file_id` is None for versions uploaded before files
    # were kept; hash and size are the draft's own, so they outlive the file.
    file_id: UUID | None = None
    file_sha256: str | None = None
    file_size: int | None = None

    def __post_init__(self) -> None:
        if self.version_number < 1:
            raise ValueError("version_number must start at 1")
        if not self.text.strip():
            raise ValueError("draft text must not be empty")
        self.filename = self.filename.strip() or "bez-nazwy"

    @property
    def has_file(self) -> bool:
        """Whether the original upload can still be downloaded."""
        return self.file_id is not None

    @property
    def char_count(self) -> int:
        """Length of the extracted text — the honest measure of a draft."""
        return len(self.text)

    @property
    def preview(self) -> str:
        """First few hundred characters, for listing versions."""
        text = self.text.strip()
        return text[:_PREVIEW_CHARS] + ("…" if len(text) > _PREVIEW_CHARS else "")
