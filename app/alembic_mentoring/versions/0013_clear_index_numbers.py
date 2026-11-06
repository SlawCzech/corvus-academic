"""clear students' index numbers

Revision ID: 0013_mentoring
Revises: 0012_mentoring
Create Date: 2026-11-06 00:00:00.000000

Corvus no longer asks for a student's index number: nothing used it, and a
datum it does not hold is one it cannot lose. The code stopped reading the
column in the same release; this empties it. The column itself goes in a
later release, so a rollback to the previous image still finds it
(docs/deploy.md, "Migracje").

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013_mentoring"
down_revision: str | Sequence[str] | None = "0012_mentoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Forget every index number."""
    op.execute("UPDATE mentoring.students SET index_number = NULL")


def downgrade() -> None:
    """Nothing to bring back: the numbers are gone."""
