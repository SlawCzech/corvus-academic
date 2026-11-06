"""Drafting a rubric from a university's regulation (ADR 0024).

The admin names the university and the kind of thesis and uploads the
regulation; the model reads it and writes the rubric in its four sections
(ADR 0023), with the thresholds. The result lands in the draft version the
regulation is attached to, where the admin checks it against the original
and publishes it. Nothing is judged by a drafted rubric until then.

The run goes through the agent like any other action, on the admin's own
provider key (ADR 0022): `start` hands it over, `refresh` — called whenever
the admin's editor reads the draft — takes the result in once it is there.
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import UUID

import structlog

from src.document.isolated import extract_upload
from src.guidelines.application.exceptions import (
    GuidelineNotFoundError,
    ProviderKeyMissingError,
)
from src.guidelines.domain.catalog import GuidelineVersion, Thresholds
from src.guidelines.domain.rubric import HEADINGS, RubricSection, parse_rubric
from src.guidelines.infrastructure.repositories import CatalogRepository
from src.shared.files import FileStore

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# A regulation runs to tens of thousands of characters; anything past this is
# not a regulation, and would only cost the admin's key.
_MAX_REGULATION_CHARS = 300_000

_FINAL_FAILURES = frozenset({"failed", "cancelled"})


@dataclass(frozen=True)
class ProviderKey:
    """The admin's own key for one provider, for one draft only."""

    provider: str
    api_key: str


# Decrypts the caller's key for one provider, or None without one. Called
# only once the provider is known, so no other key is ever opened.
KeyLoader = Callable[[str], Awaitable[ProviderKey | None]]


@dataclass(frozen=True)
class DraftingStatus:
    """What the agent says about a drafting task."""

    status: str
    output: dict[str, Any] | None
    error: str | None


class RubricDrafter(Protocol):
    """The agent, as far as drafting a rubric goes."""

    async def submit(
        self, version_id: UUID, context: dict[str, Any], key: ProviderKey, token: str
    ) -> str:
        """Queue the draft; return the task id."""
        ...

    async def status(self, task_id: str, token: str) -> DraftingStatus:
        """Read the task's state."""
        ...


class RubricDraftingService:
    """Start a draft from the attached regulation, and take its result in."""

    def __init__(
        self, repo: CatalogRepository, files: FileStore, drafter: RubricDrafter
    ) -> None:
        self._repo = repo
        self._files = files
        self._drafter = drafter

    async def start(
        self, version_id: UUID, provider: str, keys: KeyLoader, token: str
    ) -> GuidelineVersion:
        """Send the draft's regulation to the model.

        Raises GuidelineNotFoundError, VersionNotEditableError for a version
        that is not a draft or is already being drafted, ValueError for one
        with no regulation or one whose text cannot be read,
        ProviderKeyMissingError without a key for the provider, and
        DrafterUnavailableError when the agent does not take it.
        """
        version = await self._require_version(version_id)
        # Checked by the domain before the file is read or a key opened.
        source = version.require_draftable()
        stored = await self._files.get(source)
        if stored is None:
            raise ValueError("The regulation's file is gone; attach it again")
        meta, data = stored
        document = await extract_upload(data, meta.filename, meta.content_type)
        text = document.text.strip()
        if not text:
            raise ValueError("The regulation has no text to read (a scan?)")

        key = await keys(provider)
        if key is None:
            raise ProviderKeyMissingError(
                f"No {provider} key in your profile: add one to draft rubrics"
            )
        context = await self._context(version, meta.filename, text)
        task_id = await self._drafter.submit(version.id, context, key, token)
        version.start_drafting(task_id)
        await self._repo.save_version(version)
        await self._repo.commit()
        logger.info(
            "rubric_drafting_started",
            version_id=str(version.id),
            task_id=task_id,
            provider=provider,
            regulation_chars=len(text),
        )
        return version

    async def refresh(self, version_id: UUID, token: str) -> GuidelineVersion:
        """The version, with the model's rubric taken in once it is ready."""
        version = await self._require_version(version_id)
        if version.drafting_task_id is None:
            return version
        status = await self._drafter.status(version.drafting_task_id, token)
        if status.status == "completed":
            self._take_in(version, status.output)
        elif status.status in _FINAL_FAILURES:
            version.fail_drafting(status.error or "The draft did not finish")
        else:
            return version
        await self._repo.save_version(version)
        await self._repo.commit()
        logger.info(
            "rubric_drafting_finished",
            version_id=str(version.id),
            failed=version.drafting_error is not None,
        )
        return version

    async def _context(
        self, version: GuidelineVersion, filename: str, text: str
    ) -> dict[str, Any]:
        guideline_set = await self._repo.get_set(version.set_id)
        if guideline_set is None:  # pragma: no cover — a version has a set
            raise GuidelineNotFoundError(str(version.set_id))
        university = await self._repo.get_university(guideline_set.university_id)
        context: dict[str, Any] = {
            "regulation": text[:_MAX_REGULATION_CHARS],
            "regulation_filename": filename,
            "thesis_type": str(guideline_set.thesis_type),
            "university": university.name if university else "",
            "set_name": guideline_set.name,
        }
        example = await self._example(version.set_id, str(guideline_set.thesis_type))
        if example:
            context["example_rubric"] = example
        return context

    async def _example(self, set_id: UUID, thesis_type: str) -> str | None:
        """A published rubric with sections, as a model of the shape.

        Another set's for the same kind of thesis first, since its depth is
        the one wanted; then any. Never this set's own: the draft is to be
        read from the regulation, not copied from the version it replaces.
        """
        candidates: list[tuple[bool, str]] = []
        for other in await self._repo.list_sets():
            if other.id == set_id:
                continue
            current = await self._repo.published_version(other.id)
            if current is None:
                continue
            try:
                parse_rubric(current.rubric_md)
            except ValueError:
                continue
            candidates.append(
                (str(other.thesis_type) == thesis_type, current.rubric_md)
            )
        candidates.sort(key=lambda c: not c[0])
        return candidates[0][1] if candidates else None

    def _take_in(
        self, version: GuidelineVersion, output: Mapping[str, Any] | None
    ) -> None:
        try:
            rubric_md, thresholds = _rubric_from(version, output or {})
        except ValueError as exc:
            version.fail_drafting(f"The model's rubric could not be used: {exc}")
            return
        version.finish_drafting(rubric_md, thresholds)

    async def _require_version(self, version_id: UUID) -> GuidelineVersion:
        version = await self._repo.get_version(version_id)
        if version is None:
            raise GuidelineNotFoundError(str(version_id))
        return version


def _rubric_from(
    version: GuidelineVersion, output: Mapping[str, Any]
) -> tuple[str, Thresholds]:
    """The rubric's markdown and thresholds from the model's reply.

    The preamble says where the draft came from and lists the model's doubts:
    what the admin is to check before publishing. Raises ValueError when the
    sections do not make a valid rubric.
    """
    source = version.source.filename if version.source else "regulaminu"
    today = datetime.now(UTC).date().isoformat()
    preamble = [
        f"> Szkic Corvusa z pliku „{source}”, {today}. Sprawdź każdą regułę "
        "z oryginałem przed publikacją; tę notkę możesz usunąć."
    ]
    raw_doubts: Any = output.get("doubts")
    listed = cast(list[Any], raw_doubts) if isinstance(raw_doubts, list) else []
    doubts = [str(d).strip() for d in listed if str(d).strip()]
    raw: Any = output.get("thresholds")
    numbers = cast(dict[str, Any], raw) if isinstance(raw, dict) else None
    try:
        thresholds = Thresholds.from_dict(numbers)
    except (TypeError, ValueError) as exc:
        thresholds = Thresholds()
        doubts.append(f"Progi z regulaminu nie dały się zapisać ({exc}); wpisz je.")
    if doubts:
        preamble.append(">\n> Do sprawdzenia:")
        preamble.extend(f"> - {d}" for d in doubts)

    parts = ["\n".join(preamble)]
    for section in RubricSection:
        body = str(output.get(str(section)) or "").strip()
        parts.append(f"## {HEADINGS[section]}\n\n{body}")
    rubric_md = "\n\n".join(parts) + "\n"
    parse_rubric(rubric_md)
    return rubric_md, thresholds
