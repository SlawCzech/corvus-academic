# Corvus pivot: AI-first student-mentoring platform — implementation plan

> Status: approved 2026-09-05, implementation not yet started (Phase 0 pending).
> Architecture decisions referenced here are recorded as ADRs in [docs/adr/](../adr/):
> [0001](../adr/0001-ai-first-mentoring-platform-pivot.md) (scope pivot),
> [0002](../adr/0002-consolidate-services-into-app-and-agent.md) (service consolidation),
> [0003](../adr/0003-postgres-pgvector-for-persistence-and-rag.md) (Postgres/pgvector),
> [0004](../adr/0004-self-hosted-default-model-with-byok.md) (model strategy/BYOK),
> [0005](../adr/0005-predefined-actions-not-open-chat.md) (predefined actions, not chat).
> This document is the working implementation reference for the build sessions ahead — update it as phases land, the way `docs/sessions.md`'s "Stan projektu" table tracks the older session plan.

## Context

Corvus started as a PoC: upload one thesis, run a fixed 4-node LangGraph pipeline, get a review. The user decided to pivot it into a real (informally deployed, small trusted user group) app where a promoter manages **Students** over the full thesis lifecycle — meeting notes, topic proposals, methodology checks, progress/change tracking, and a final formal+substantive review. The explicit motivation is educational: maximize exposure to production AI-app patterns (LangGraph, tool use, structured output, BYOK, eventually LangSmith evals) rather than DDD/microservices practice, which was the original educational framing.

The following decisions are **final** (see ADRs linked above) — this plan implements them, it does not re-litigate them:

1. Consolidate the current 4 Python services (`gateway`, `identity`, `parser`, `agent`) into **2**: `app` (everything fast/synchronous — identity, auth, students, notes) and `agent` (everything slow/async — LangGraph + Celery).
2. Database stays **Postgres**; add **pgvector** later for guideline RAG, no new datastore.
3. Model strategy: self-hosted Ollama as the privacy-preserving default, **BYOK** (user's own Anthropic/OpenAI key) as opt-in, no centrally-held key.
4. Interface: **predefined, repeatable actions** (not open chat) — but context-gathering code must be modular enough to become "tools" for a future chat agent without a rewrite.
5. `identity`'s domain (roles, permissions, audit log, bans) is kept — the user explicitly wants admin visibility/ban capability — just merged into `app`, not deleted.

A dedicated planning pass explored the actual codebase and surfaced three concrete findings that shape sequencing below:

- **Gateway does no JWT verification at all** — it's a dumb `httpx` proxy (`gateway/src/infrastructure/router.py`). Deleting it is purely mechanical; there's no auth logic to preserve.
- **BYOK storage exists but is inert**: `PATCH /settings/api-key` (`identity/src/infrastructure/router.py:330`) is admin-only today, `ApiKeyRequest.provider` is logged but never persisted (no column for it), and `agent/src/infrastructure/llm_factory.py::get_llm()` never reads a user's key at all. Phase 4 has real wiring work, not just plumbing.
- **`AnalysisModel.status` is written once (`"PENDING"`) and never updated** (`agent/src/infrastructure/api/router.py::submit_analysis` / `tasks.py`) — status is read live from Celery's Redis result backend, which expires (~1 day default). This breaks the pivot's "history over time" requirement and must be fixed in Phase 2, not deferred.

---

## Target data model — new `mentoring` Postgres schema

Four tables, decided as **one generic AI-action log + three first-class human-authored tables** (not five near-identical per-action tables): every action type shares the same trigger→dispatch→poll→structured-output→accept lifecycle already proven by today's `AnalysisModel`, and JSONB absorbs the prompt-shape churn expected during Phase 2-3 iteration without an Alembic migration every time.

```
mentoring.students        -- roster entry: id, promotor_id (uuid, NO FK — cross-context),
                              full_name, index_number, field_of_study, thesis_type,
                              current_topic, current_topic_set_at, status, timestamps

mentoring.thesis_drafts   -- uploaded document versions: id, student_id (FK, same context),
                              version_number, filename, text, pages, format, uploaded_by, created_at
                              UNIQUE(student_id, version_number)

mentoring.meeting_notes   -- human-approved notes: id, student_id (FK), promotor_id, occurred_at,
                              content, source_action_id (FK to agent_actions, nullable — provenance
                              when AI-drafted), created_at

mentoring.agent_actions   -- generic AI action log: id, student_id (FK), promotor_id, action_type
                              (propose_topic|evaluate_methodology|check_progress|draft_meeting_note|
                              generate_review), status, task_id, detail, input_ref (jsonb, IDs only),
                              output (jsonb), accepted, accepted_at, error, timestamps
                              INDEX(student_id, action_type, created_at desc), INDEX(task_id)
```

Cross-context references (`promotor_id`, `uploaded_by`) stay plain UUIDs with no FK — this extends the *existing, deliberate* precedent already in `agent/src/infrastructure/models.py::AnalysisModel` (`"user_id is a plain UUID — no FK to identity.users (cross-service boundary)"`). Within `mentoring` itself, real FKs are used (it's one bounded context).

Only `students.current_topic` gets denormalized "current state" treatment (per the explicit requirement); everything else stays queryable as history via `agent_actions` filtered by `(student_id, action_type)`.

**Migrations**: two independent Alembic lineages inside `app/` (`alembic_identity/`, moved verbatim from `identity/alembic/`; `alembic_mentoring/`, new), each scoped to one schema — this directly extends the `include_object`/`version_table_schema` pattern already used identically in `identity/alembic/env.py` and `agent/alembic/env.py`. `app/entrypoint.sh` runs both lineages before starting uvicorn.

---

## Merging `gateway` + `identity` + `parser` → `app`

Target layout:

```
app/
  main.py, pyproject.toml, Dockerfile, entrypoint.sh
  alembic_identity/, alembic_mentoring/
  scripts/seed_admin.py                    # moved from identity/scripts/
  src/
    identity/{domain,application,infrastructure}/   # = identity/src/*, moved verbatim, imports updated
    document/{document.py,extractor.py}              # = parser/src/{domain,application}/*, moved verbatim
                                                       # parser's infrastructure/router.py is DELETED —
                                                       # extraction becomes an in-process function call,
                                                       # no more /extract HTTP hop
    mentoring/{domain,application,infrastructure}/    # new bounded context (see data model above)
    shared/{settings.py,database.py,logging.py,middleware.py}  # hoisted out of what's currently
                                                       # duplicated near-verbatim across identity/agent/gateway
  tests/{test_identity,test_document,test_mentoring}/ # moved tests get import-path updates only,
                                                       # no logic changes; conftest.py merges schema_translate_map
                                                       # to {"identity": None, "mentoring": None}
                                                       # (extends identity/tests/conftest.py's existing pattern)
```

`agent` is untouched by this merge — it keeps its own `pyproject.toml`, Dockerfile, Postgres schema (`analysis`), and Alembic lineage.

Mechanical steps: scaffold `app/` → move identity's 3 layers + parser's domain/application (no router) → extract `shared/*` (settings/database/logging/middleware are each duplicated across services today, this is consolidation not new design) → new `main.py` wiring `include_router` for identity + mentoring, one `httpx.AsyncClient` in app state for calling `agent` (replaces `gateway/src/infrastructure/router.py::_proxy`) → build the two Alembic lineages → update `infra/docker-compose.yml` (remove `gateway`/`identity`/`parser` blocks, add one `app` block) and `.env.example` (drop `IDENTITY_URL`, add `ENVIRONMENT=local`) → only delete the old `gateway/`, `identity/`, `parser/` directories once `app`'s test suite is green and reproduces their combined coverage.

Also fold in now (cheap while `shared/settings.py` is being written anyway): the `ENVIRONMENT=local|production` flag, and fix `identity/src/infrastructure/router.py`'s hardcoded `secure=True` cookie flag (lines 188/236) to `secure=(settings.environment == "production")` — otherwise a non-HTTPS local/dev deployment silently drops the refresh cookie.

**Verification**: `uv run pytest app/tests -v --cov=src` reproduces identity's 61 + parser's 14 test counts (minus the deleted `test_router.py` for parser) at ≥80% coverage; `ruff check` + `pyright` clean; `docker compose config` validates; `docker compose up --build` brings up `app`+`agent`+`agent-worker`+`postgres`+`redis` with passing healthchecks; manually confirm `POST /auth/login` still works end-to-end through `app`.

---

## Action catalog in `agent`

`AnalysisState` (today: flat keys `text`/`guidelines`/`metadata`) generalizes to `ActionState`, moving action-specific payload into a `context: dict[str, Any]` key:

```python
class ActionState(TypedDict):
    action_id: str          # mentoring.agent_actions.id, for log correlation
    action_type: str
    student_id: str
    context: dict[str, Any] # text, guidelines, prior_findings, detail, current_topic, ...
    findings: list[Finding]
    scores: list[Score]
    output: dict[str, Any] | None
    status: str
    error: str | None
    model: str
    language: str
```

This touches all four existing node files (`nodes/{structure,methodology,requirements,review}.py` — change `state["text"]` → `state["context"]["text"]` etc., following the exact try/except-never-raises pattern already established in `nodes/structure.py`), `state.py`, `graph.py`, `tasks.py`, and their tests — mechanical but real churn; flagged as the main regression-risk area.

**Contract** (generalizes today's `POST /analysis` in `agent/src/infrastructure/api/router.py`):

```python
class ActionRequest(BaseModel):
    action_type: str
    student_id: str
    action_id: str
    detail: str | None = None
    context: dict[str, Any]          # assembled entirely by `app`, see below
    model: str = "qwen3:30b-a3b"
    language: str = "pl"
    byok: BYOKConfig | None = None   # {"provider": ..., "api_key": ...} — Phase 4
```

`POST /actions` + `GET /actions/{task_id}` replace `POST/GET /analysis` — same 202-then-poll shape the frontend's `useAnalysis` hook already implements, so that hook generalizes to `useAction(actionId)` without a redesign.

**Graph dispatch**: `generate_review` delegates wholesale to the *existing* `build_analysis_graph(mode="full")` — unchanged, it's already exactly the final action. `evaluate_methodology` reuses `nodes/methodology.py::analyze_methodology` near-verbatim after the context-key refactor. `propose_topic`, `check_progress`, `draft_meeting_note` are new one-node graphs following the identical two-file pattern every existing action uses (node file + prompt file, e.g. `nodes/structure.py` + `prompts/structure.py`).

**Context-gathering happens entirely in `app`, `agent` never calls back** — justified because: `agent` has zero precedent for depending on external services mid-task today (every node is a pure function of state); a callback would make Celery workers depend on `app`'s uptime for unrelated jobs; no existing agent test mocks HTTP, only `get_llm()`; and `app` already holds the DB session and student history in-process post-merge, so gathering context there is strictly cheaper. Concretely: `app/src/mentoring/application/context.py` gets one assembly function per action type (e.g. `assemble_check_progress_context(student_id)` fetches only the latest 2 `ThesisDraft` rows, not full history) — this is also the exact seam that lets a future chat agent reuse the same functions as tools without a rewrite.

---

## BYOK wiring — call path

1. `app`'s action-submission endpoint loads the calling user's `UserModel` in-process (no more network hop to identity), decrypts `api_key_encrypted` via the existing `SecretService`/Fernet (`identity/src/infrastructure/secrets.py`, unchanged) if present, reads the new `api_key_provider` column.
2. `app` calls `agent`'s `POST /actions` including `byok` when present, via `mentoring/application/agent_client.py` (direct replacement for `gateway`'s `proxy_agent_analysis`, same `AGENT_URL` setting).
3. `agent`'s Celery task receives `api_key`/`provider` as **separate task kwargs, never placed inside `ActionState`** — deliberate, because `tasks.py::_to_json` currently serializes the *entire* final state into the persisted result; keeping the key out of state means it can never leak into `agent_actions.output`.
4. `llm_factory.get_llm()` (today: `get_llm(model_override: str | None = None)`) gains `api_key`/`provider` params, checked *before* the existing `settings.model_backend` match — BYOK wins, Ollama is the fallback, matching the current function's existing structure exactly.
5. `PATCH /settings/api-key` changes `Depends(require_admin)` → `Depends(get_current_user)` (currently admin-only per `identity/tests/test_router.py::test_set_api_key_promotor_forbidden`, which gets replaced with a success-path test) and actually persists `provider` via a new `api_key_provider` column (`app/alembic_identity/versions/0002_add_api_key_provider.py`).

---

## Phased build order

Sequencing follows the user's "AI first, simple interface" preference: Phase 0 is a fast, low-risk mechanical prerequisite (so the new domain has the right home instead of being built on services about to be torn down); Phase 1 is deliberately minimal; real investment goes into Phase 2's AI slice.

| Phase | Status |
|---|---|
| 0 — service consolidation | ✅ done 2026-09-05 (81 tests, 88.3% cov, ruff clean) |
| 1 — Student + MeetingNote backbone | ⬜ not started |
| 2 — first AI action end-to-end (`propose_topic`) | ⬜ not started |
| 3 — remaining actions | ⬜ not started |
| 4 — BYOK wiring | ⬜ not started |
| 5 — pgvector RAG for guidelines | ⬜ not started |
| 6 — deploy/CI groundwork | ⬜ not started |

**Phase 0 — service consolidation** — ✅ **done 2026-09-05**. Deviations from the plan as written, all deliberate:

1. **`/extract` and the `/analysis/*` proxy were kept, not deleted.** The plan had parser's router deleted immediately and extraction called in-process. Doing that in Phase 0 would have broken the existing frontend analysis flow for Phases 1–3, since the mentoring endpoints that replace it don't exist yet. Both live on in `app/src/document/router.py` and `app/src/proxy/` marked TRANSITIONAL, and are deleted in Phase 3. Consequence: parser's `test_router.py` survived too, so `app` reproduces more of the old coverage than planned.
2. **`/internal/users/{id}` and `/internal/token/introspect` were deleted** (identity router). Their only protection was that gateway didn't proxy them; mounted on the merged public port they would have been an unauthenticated user lookup and a public token oracle. Nothing called them — `agent` verifies JWT locally. Replaced by a test asserting they 404.
3. **`fastapi` and `starlette` pinned exactly** (`==0.136.3` / `==1.2.1`). A fresh lockfile resolved them to 0.141 / 1.6, folding an untested dependency upgrade into a structural refactor.
4. **Frontend left untouched.** `GATEWAY_URL` and `PARSER_URL` both now point at `app:8000` via compose. Collapsing them into one `APP_URL` is frontend churn better done in Phase 3 when those route handlers get rewritten anyway.
5. **`Makefile`'s `migrate` target fixed in passing** — it referenced a `migrate` compose service that has not existed for some time; now runs alembic inside `app`.

**Finding that invalidates a plan assumption:** the plan's verification step assumed `ruff` and `pyright` were clean before Phase 0, per `docs/sessions.md`. Measured on pre-refactor `HEAD` via a git worktree, they were not: `identity` had **736** pyright errors and 6 ruff errors, `parser` had **88** pyright errors. `app` now has 160 pyright errors and 0 ruff. Pyright strict has therefore never passed on this codebase; treat "pyright clean" in `docs/sessions.md` as aspirational. Recorded in `docs/technical-debt.md` — fix deliberately, not inside a refactor.

Critical files: `app/pyproject.toml`, `app/main.py`, `app/src/shared/*`, `app/alembic_identity/`, `infra/docker-compose.yml`.

**Phase 1 — minimal Student + MeetingNote backbone**. `app/src/mentoring/domain/student.py`, `infrastructure/models.py` (all 4 tables, `agent_actions` created now even though unused until Phase 2 — one migration), `alembic_mentoring/versions/0001_initial_mentoring_schema.py`, `infrastructure/router.py` (`POST/GET /students`, `POST /students/{id}/meeting-notes`), new `Permission.MANAGE_STUDENTS` in `identity/domain/user.py::_ROLE_PERMISSIONS`. Verification: domain + repository + router tests (ownership check: promoter sees only their students, admin sees all), manual `curl` smoke test.

**Phase 2 — one full AI action end-to-end (proof slice): `propose_topic`.** Recommended first slice because it needs no document upload, no guidelines file, no accumulated findings — just a `Student` row and optional free text. Exercises the entire new pipeline shape (button → context assembly → HTTP call → Celery → LLM → structured output → poll → human review/accept → `Student.current_topic` update) before any other action reuses it. Also **fixes the status-persistence bug**: `agent`'s task must write `status`/`output` back to its own Postgres row (renamed `AnalysisModel`→`AgentTaskModel`, `+action_type` column) on completion, not rely solely on Celery's Redis result TTL. Files: `agent/src/application/state.py` (→`ActionState`), `nodes/propose_topic.py` + `prompts/propose_topic.py`, `graph.py::build_action_graph`, `tasks.py` (generalize + persist status), `infrastructure/api/router.py` (`POST/GET /actions`), `app/src/mentoring/application/{context,agent_client,action_service}.py`, `app/src/mentoring/infrastructure/router.py` (`POST /students/{id}/actions`, `PATCH .../accept`). Verification: node test mirroring `test_structure_node.py`'s 3-case style, graph test, router test, **a durability regression test** (clear Redis, confirm Postgres still has the right status), manual end-to-end run via `docker compose up`.

**Phase 3 — remaining actions**: `check_progress.py` + prompt, `draft_meeting_note.py` + prompt (new); `evaluate_methodology` reuses `methodology.py`; `generate_review` reuses `build_analysis_graph(mode="full")` unchanged. `POST /students/{id}/drafts` upload endpoint calls `app/src/document/extractor.py` in-process (the merge's concrete payoff — no more `/extract` HTTP hop). One context-assembly function per action type. Verification: per-action node tests + one full `app→agent→back` integration test per action (mirroring `agent/tests/test_application/test_tasks.py`'s eager-Celery setup); manual run of all 5 actions against a student with 2 draft versions.

**Phase 4 — BYOK wiring** (§ above). Verification: `llm_factory` tests for the BYOK-present branch, the admin-only→any-user auth-change test, and a test asserting the key never appears in persisted JSON output.

**Phase 5 — pgvector RAG for guidelines**: embeddings table lives in `agent`'s own `analysis` schema (guidelines are static files `agent` already owns) — `guideline_chunks(id, thesis_type, chunk_text, embedding vector(N))`, ingestion script, `guidelines.py::retrieve_relevant_guidelines()` used by `check_requirements`/`generate_review` instead of loading the whole file.

**Phase 6 — deploy/CI groundwork**: revisit `docs/sessions.md` §5.2/5.3 (never implemented) for the new 2-Python-service topology — `.github/workflows/ci.yml` with `test-app`+`test-agent`+`test-frontend`+`sonarqube` jobs, `.pre-commit-config.yaml`, `infra/jenkins/Jenkinsfile` reduced from 4 to 2 Python stages. Cloud/secret-manager choice deliberately left open here, not pre-committed.

**Frontend** (not designed in detail — existing patterns extend directly): `GATEWAY_URL`/`PARSER_URL` → single `APP_URL`; new route handlers mirroring existing ones 1:1 (`app/api/students/...`, following `app/api/status/[taskId]/route.ts`'s polling shape); `useAnalysis.ts` generalizes to `useAction(actionId)`. Note: `frontend/AGENTS.md` warns this Next.js version has non-standard APIs vs. training data — read `node_modules/next/dist/docs/` before writing route handlers.

---

## Verification summary

Each phase lists its own tests above; overall gate before moving to the next phase: `uv run pytest -v --cov=src` (≥80%) + `ruff check` + `pyright` clean in the touched service(s), plus one manual end-to-end smoke test through `docker compose up`. No phase is "done" on unit tests alone given how much of this plan is cross-service wiring.
