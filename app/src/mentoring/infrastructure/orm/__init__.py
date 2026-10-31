"""SQLAlchemy 2.0 ORM models for the mentoring bounded context.

All tables live in the ``mentoring`` PostgreSQL schema, separate from
``identity`` — one schema per bounded context, migrated by its own Alembic
lineage (``alembic_mentoring/``).

Cross-context columns (``promotor_id``, ``uploaded_by``) are plain UUIDs with
no foreign key: they point at ``identity.users``, and contexts are not joined
across the boundary. Inside ``mentoring`` real foreign keys are used — it is
one context, one schema, one migration lineage.

One file per aggregate, mirroring ``domain/`` exactly — ``student.py`` holds
both ``StudentModel`` and ``MeetingNoteModel``, the same pairing as
``domain.student``'s ``Student``/``MeetingNote``. This module re-exports all
of them: every model must be imported somewhere before Alembic or
``Base.metadata.create_all`` reads ``Base.metadata``, so importing this
package — rather than a specific submodule — is what guarantees every table
is registered. That guarantee is the one thing splitting the classes across
files must not break.
"""

from src.mentoring.infrastructure.orm.action import AgentActionModel
from src.mentoring.infrastructure.orm.base import Base
from src.mentoring.infrastructure.orm.draft import DraftFileModel, ThesisDraftModel
from src.mentoring.infrastructure.orm.fragment import (
    ThesisFragmentModel,
    ThesisPartModel,
)
from src.mentoring.infrastructure.orm.model_setting import ModelSettingModel
from src.mentoring.infrastructure.orm.student import MeetingNoteModel, StudentModel

__all__ = [
    "AgentActionModel",
    "Base",
    "DraftFileModel",
    "MeetingNoteModel",
    "ModelSettingModel",
    "StudentModel",
    "ThesisDraftModel",
    "ThesisFragmentModel",
    "ThesisPartModel",
]
