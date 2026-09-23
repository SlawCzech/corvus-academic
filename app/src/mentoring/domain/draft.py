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

    A purged version keeps its row — number, date, filename, hash, size and
    length — and loses its text and file. The action history still says which
    version each result was about; the thesis itself is gone.
    """

    id: UUID
    student_id: UUID
    version_number: int
    filename: str
    text: str | None
    pages: int
    format: str
    uploaded_by: UUID
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # The original upload. `file_id` is None for versions uploaded before files
    # were kept; hash and size are the draft's own, so they outlive the file.
    file_id: UUID | None = None
    file_sha256: str | None = None
    file_size: int | None = None
    # Stored rather than derived, so a purged version still reports it.
    char_count: int = 0
    purged_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.version_number < 1:
            raise ValueError("version_number must start at 1")
        if self.purged_at is None and not (self.text or "").strip():
            raise ValueError("draft text must not be empty")
        if self.text is not None:
            self.char_count = len(self.text)
        self.filename = self.filename.strip() or "bez-nazwy"

    @property
    def is_purged(self) -> bool:
        """Whether the text and file have been removed under retention."""
        return self.purged_at is not None

    @property
    def has_file(self) -> bool:
        """Whether the original upload can still be downloaded."""
        return self.file_id is not None

    @property
    def content(self) -> str:
        """The extracted text. Asking a purged version for it is a bug."""
        if self.text is None:
            raise ValueError(f"Draft {self.id} has been purged")
        return self.text

    @property
    def preview(self) -> str:
        """First few hundred characters, for listing versions."""
        text = (self.text or "").strip()
        return text[:_PREVIEW_CHARS] + ("…" if len(text) > _PREVIEW_CHARS else "")

    def purge(self, at: datetime) -> None:
        """Drop the text and the file reference; keep everything else."""
        self.text = None
        self.file_id = None
        self.purged_at = at
