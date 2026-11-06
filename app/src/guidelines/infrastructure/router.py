"""HTTP API of the guideline catalog.

Reads under ``/guidelines`` — for promoters and admins. Writes under
``/guidelines/admin`` — for whoever holds ``MANAGE_GUIDELINES``. Application
exceptions are mapped onto status codes here, once.
"""

import uuid
from collections.abc import Awaitable
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, UploadFile, status

from src.guidelines.application.exceptions import (
    DrafterUnavailableError,
    GuidelineConflictError,
    GuidelineNotFoundError,
    ProviderKeyMissingError,
)
from src.guidelines.domain.catalog import ThesisType, VersionNotEditableError
from src.guidelines.infrastructure.dependencies import (
    AdminServiceDep,
    BearerTokenDep,
    CatalogDep,
    DraftingServiceDep,
    GuidelineAdminDep,
    KeyLoaderDep,
    ReaderDep,
)
from src.guidelines.infrastructure.schemas import (
    DraftCreateRequest,
    DraftRubricRequest,
    DraftUpdateRequest,
    SetCreateRequest,
    SetDetailResponse,
    SetResponse,
    UniversityCreateRequest,
    UniversityResponse,
    VersionResponse,
    set_detail_response,
    set_response,
    university_response,
    version_response,
)
from src.shared.downloads import attachment_response, read_upload

router = APIRouter(prefix="/guidelines", tags=["guidelines"])


async def _guarded[T](call: Awaitable[T]) -> T:
    """Run a use case, translating its business outcomes into HTTP."""
    try:
        return await call
    except GuidelineNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Not found: {exc}") from exc
    except ProviderKeyMissingError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except DrafterUnavailableError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The drafting service is not available"
        ) from exc
    except (GuidelineConflictError, VersionNotEditableError) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


# ---------- read ----------


@router.get("/universities", response_model=list[UniversityResponse])
async def list_universities(
    _reader: ReaderDep, catalog: CatalogDep
) -> list[UniversityResponse]:
    return [university_response(u) for u in await catalog.list_universities()]


@router.get("/sets", response_model=list[SetResponse])
async def list_sets(
    reader: ReaderDep,
    catalog: CatalogDep,
    thesis_type: Annotated[ThesisType | None, Query()] = None,
) -> list[SetResponse]:
    """Every set with its version in force; drafts only for catalog admins."""
    summaries = await catalog.list_sets(
        str(thesis_type) if thesis_type else None, include_drafts=reader.can_manage
    )
    return [set_response(s) for s in summaries]


@router.get("/sets/{set_id}", response_model=SetDetailResponse)
async def get_set(
    set_id: uuid.UUID, reader: ReaderDep, catalog: CatalogDep
) -> SetDetailResponse:
    """A set with its version history, newest first."""
    detail = await _guarded(catalog.get_set_detail(set_id, reader.can_manage))
    return set_detail_response(detail)


@router.get("/versions/{version_id}", response_model=VersionResponse)
async def get_version(
    version_id: uuid.UUID, reader: ReaderDep, catalog: CatalogDep
) -> VersionResponse:
    detail = await _guarded(catalog.get_version(version_id, reader.can_manage))
    return version_response(detail)


@router.get("/versions/{version_id}/source")
async def download_source(
    version_id: uuid.UUID, reader: ReaderDep, catalog: CatalogDep
) -> Response:
    """The original regulation, as an attachment."""
    stored, data = await _guarded(
        catalog.download_source(version_id, reader.can_manage)
    )
    return attachment_response(stored, data)


# ---------- admin ----------


@router.post(
    "/admin/universities",
    response_model=UniversityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_university(
    body: UniversityCreateRequest, _admin: GuidelineAdminDep, svc: AdminServiceDep
) -> UniversityResponse:
    university = await _guarded(svc.create_university(body.name, body.short_name))
    return university_response(university)


@router.post(
    "/admin/sets", response_model=SetDetailResponse, status_code=status.HTTP_201_CREATED
)
async def create_set(
    body: SetCreateRequest,
    _admin: GuidelineAdminDep,
    svc: AdminServiceDep,
    catalog: CatalogDep,
) -> SetDetailResponse:
    created = await _guarded(
        svc.create_set(body.university_id, body.thesis_type, body.name)
    )
    return set_detail_response(await catalog.get_set_detail(created.id, True))


@router.post(
    "/admin/sets/{set_id}/versions",
    response_model=VersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_draft(
    set_id: uuid.UUID,
    body: DraftCreateRequest,
    admin: GuidelineAdminDep,
    svc: AdminServiceDep,
    catalog: CatalogDep,
) -> VersionResponse:
    """Open the next version as a draft, starting from the one in force."""
    draft = await _guarded(
        svc.create_draft(
            set_id,
            admin.id,
            rubric_md=body.rubric_md,
            thresholds=body.thresholds.to_domain() if body.thresholds else None,
            effective_from=body.effective_from,
        )
    )
    return version_response(await catalog.get_version(draft.id, True))


@router.patch("/admin/versions/{version_id}", response_model=VersionResponse)
async def update_draft(
    version_id: uuid.UUID,
    body: DraftUpdateRequest,
    _admin: GuidelineAdminDep,
    svc: AdminServiceDep,
    catalog: CatalogDep,
) -> VersionResponse:
    """Change a draft; a published version answers 409."""
    await _guarded(
        svc.edit_draft(
            version_id,
            rubric_md=body.rubric_md,
            thresholds=body.thresholds.to_domain() if body.thresholds else None,
            effective_from=body.effective_from,
        )
    )
    return version_response(await catalog.get_version(version_id, True))


@router.put("/admin/versions/{version_id}/source", response_model=VersionResponse)
async def upload_source(
    version_id: uuid.UUID,
    file: UploadFile,
    _admin: GuidelineAdminDep,
    svc: AdminServiceDep,
    catalog: CatalogDep,
) -> VersionResponse:
    """Attach the original regulation (PDF/DOCX) to a draft."""
    data = await read_upload(file)
    await _guarded(
        svc.attach_source(
            version_id, file.filename or "", data, file.content_type or ""
        )
    )
    return version_response(await catalog.get_version(version_id, True))


@router.post(
    "/admin/versions/{version_id}/draft-rubric",
    response_model=VersionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def draft_rubric(
    version_id: uuid.UUID,
    body: DraftRubricRequest,
    _admin: GuidelineAdminDep,
    drafting: DraftingServiceDep,
    keys: KeyLoaderDep,
    token: BearerTokenDep,
    catalog: CatalogDep,
) -> VersionResponse:
    """Have the model draft the rubric from the attached regulation (ADR 0024).

    Runs on the admin's own key for the provider. The draft fills in when
    `GET /admin/versions/{id}` finds the run finished.
    """
    await _guarded(drafting.start(version_id, body.provider, keys, token))
    return version_response(await catalog.get_version(version_id, True))


@router.get("/admin/versions/{version_id}", response_model=VersionResponse)
async def read_draft(
    version_id: uuid.UUID,
    _admin: GuidelineAdminDep,
    drafting: DraftingServiceDep,
    token: BearerTokenDep,
    catalog: CatalogDep,
) -> VersionResponse:
    """A version as the admin edits it, with a drafted rubric taken in."""
    await _guarded(drafting.refresh(version_id, token))
    return version_response(await catalog.get_version(version_id, True))


@router.post("/admin/versions/{version_id}/publish", response_model=VersionResponse)
async def publish_version(
    version_id: uuid.UUID,
    admin: GuidelineAdminDep,
    svc: AdminServiceDep,
    catalog: CatalogDep,
) -> VersionResponse:
    """Publish a draft; the version in force becomes superseded."""
    await _guarded(svc.publish(version_id, admin.id))
    return version_response(await catalog.get_version(version_id, True))
