# Corvus pivot: AI-first student-mentoring platform — implementation plan

> Status: approved 2026-09-05. All six phases are done.
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
| 1 — Student + MeetingNote backbone | ✅ done 2026-09-05 (150 tests, 90.4% cov, ruff clean) |
| 2 — first AI action end-to-end (`propose_topic`) | ✅ done 2026-09-05 (310 tests, ruff clean) |
| 3 — remaining actions + drafts + removing the transitional endpoints | ✅ done 2026-09-06 |
| 4 — BYOK wiring | ✅ done 2026-09-06 |
| 5 — pgvector RAG for guidelines | ✅ done 2026-09-06 |
| 6 — deploy/CI groundwork | ✅ done 2026-09-06 |

**Phase 0 — service consolidation** — ✅ **done 2026-09-05**. Deviations from the plan as written, all deliberate:

1. **`/extract` and the `/analysis/*` proxy were kept, not deleted.** The plan had parser's router deleted immediately and extraction called in-process. Doing that in Phase 0 would have broken the existing frontend analysis flow for Phases 1–3, since the mentoring endpoints that replace it don't exist yet. Both live on in `app/src/document/router.py` and `app/src/proxy/` marked TRANSITIONAL, and are deleted in Phase 3. Consequence: parser's `test_router.py` survived too, so `app` reproduces more of the old coverage than planned.
2. **`/internal/users/{id}` and `/internal/token/introspect` were deleted** (identity router). Their only protection was that gateway didn't proxy them; mounted on the merged public port they would have been an unauthenticated user lookup and a public token oracle. Nothing called them — `agent` verifies JWT locally. Replaced by a test asserting they 404.
3. **`fastapi` and `starlette` pinned exactly** (`==0.136.3` / `==1.2.1`). A fresh lockfile resolved them to 0.141 / 1.6, folding an untested dependency upgrade into a structural refactor.
4. **Frontend left untouched.** `GATEWAY_URL` and `PARSER_URL` both now point at `app:8000` via compose. Collapsing them into one `APP_URL` is frontend churn better done in Phase 3 when those route handlers get rewritten anyway.
5. **`Makefile`'s `migrate` target fixed in passing** — it referenced a `migrate` compose service that has not existed for some time; now runs alembic inside `app`.

**Finding that invalidates a plan assumption:** the plan's verification step assumed `ruff` and `pyright` were clean before Phase 0, per `docs/sessions.md`. Measured on pre-refactor `HEAD` via a git worktree, they were not: `identity` had **736** pyright errors and 6 ruff errors, `parser` had **88** pyright errors. `app` now has 160 pyright errors and 0 ruff. Pyright strict has therefore never passed on this codebase; treat "pyright clean" in `docs/sessions.md` as aspirational. Recorded in `docs/technical-debt.md` — fix deliberately, not inside a refactor.

Critical files: `app/pyproject.toml`, `app/main.py`, `app/src/shared/*`, `app/alembic_identity/`, `infra/docker-compose.yml`.

**Phase 1 — minimal Student + MeetingNote backbone** — ✅ **done 2026-09-05**. Built as planned: `app/src/mentoring/{domain/student.py,application/student_service.py,infrastructure/{models,repositories,router}.py}`, all four tables in `alembic_mentoring/versions/0001_initial_mentoring_schema.py`, `Permission.MANAGE_STUDENTS` added to `identity/domain/user.py::_ROLE_PERMISSIONS`. 69 new tests (150 total in `app`, 90.4% coverage), `ruff` clean, `pyright` clean on `src/mentoring`. Verified end-to-end against the real stack: both Alembic lineages run from `entrypoint.sh`, the four tables exist in Postgres with their FKs, and login → create student → list → set topic → add note → list notes works over HTTP (smoke data deleted afterwards; the cascade to `meeting_notes` was confirmed by that delete).

Deviations from the plan as written, all deliberate:

1. **A second permission, `VIEW_ALL_STUDENTS`, was added.** The plan named only `MANAGE_STUDENTS`, but admin holds every permission by construction (`frozenset(Permission)`), so that one permission cannot express "promoter sees only their own roster, admin sees all". `VIEW_ALL_STUDENTS` mirrors the existing `VIEW_ALL_ANALYSES` exactly, so the rule is data, not an `if role == ADMIN` branch.
2. **`GET /students/{id}` and `PATCH /students/{id}` added** beyond the listed endpoints. Without a read-one endpoint the roster is not usable, and `PATCH` (topic/status) is what gives `Student.set_topic()` a caller before Phase 2 — the same field the accepted `propose_topic` action will write.
3. **Invisible students return 404, not 403**, so a promoter cannot probe whether another promoter's student id exists. One `StudentNotFoundError` covers "does not exist" and "not yours".
4. **`Caller(user_id, can_view_all)` instead of passing identity's `User` into `mentoring`.** The service needs who is acting and whether they may look past their own roster; the router does the permission lookup. Keeps the mentoring context free of identity imports, matching the plain-UUID cross-context rule.
5. **Application-layer unit tests added (`test_student_service.py`)**, not just domain/repository/router. Coverage in this repo does not trace async endpoint bodies executed inside `TestClient`'s worker thread — identity's `/auth/login` shows as uncovered for the same reason — so the ownership rule is tested directly as well as over HTTP. That is also how identity's application layer is tested.
6. **Dockerfile, `docker-compose.override.yml` and `make migrate` updated** to carry the second Alembic lineage — the plan mentioned only `entrypoint.sh`.

**Phase 2 — one full AI action end-to-end (proof slice): `propose_topic`** — ✅ **done 2026-09-05**. The whole loop runs: button → context assembly in `app` → `POST /actions` → Celery → LangGraph → structured output → poll → accept → `Student.current_topic`. Built as planned, including the status-persistence fix.

Verified against the running stack with the real model (qwen3:30b-a3b on the host's Ollama), not only in tests: a student with one meeting note and the promoter's instruction ("temat z komponentem ilościowym") produced three concrete Polish topics with rationale/scope/risks that visibly used both the note and the instruction; accepting index 1 set `students.current_topic` and stamped `current_topic_set_at`; a second accept returned 409. **The durability fix was then proved by deleting every `celery-task-meta-*` key from Redis — the action still reported `completed` with all three topics.** The legacy `POST /analysis` flow was re-run end-to-end afterwards to confirm the state refactor did not break it. Smoke data deleted; the one pre-existing legacy row was migrated in place (`PENDING` → `pending`, `action_type='generate_review'`) and left alone.

Files: `agent/src/domain/action.py` (new — `ActionType`, `TaskStatus`), `agent/src/infrastructure/{models,repositories,task_status}.py`, `agent/alembic/versions/0002_agent_tasks.py`, `agent/src/application/{state,graph,tasks}.py`, `agent/src/application/nodes/propose_topic.py` + `prompts/propose_topic.py`, `agent/src/infrastructure/api/router.py`; `app/src/mentoring/domain/action.py` (new — `AgentAction`), `app/src/mentoring/application/{context,agent_client,action_service}.py`, `app/src/mentoring/infrastructure/{repositories,router}.py`.

Decisions worth recording:

1. **`analyses` → `agent_tasks`, and the worker writes its own status.** `status` was set once to `"PENDING"` and never updated; the live value came from Celery's Redis backend. Now the task writes `running` → `completed`/`failed` to Postgres and the API reads only from there. The row is also created *before* dispatch, under a caller-generated `task_id`, so a fast task can never outrun the row it must update. Status vocabulary is the mentoring one (`pending|running|completed|failed`); the legacy `/analysis` endpoints translate at the boundary to what the frontend already reads.
2. **A node error is a failed task, not a done one with an empty result.** Nodes never raise — they record the problem in state and let the graph finish — so an error surviving to the end now marks the task `failed` with that message, instead of returning `done` and an empty review.
3. **The result payload is trimmed before it is stored.** The task used to return the entire graph state, thesis text and guidelines included; that is now dropped, so a 2 MB thesis no longer travels into JSONB, Redis and the HTTP response.
4. **`analyze_thesis` was kept as a thin adapter over the new machinery**, rather than being generalized away. It builds the same `ActionState` and runs the same graph, so there is one implementation, while the pre-mentoring upload flow keeps working untouched until Phase 3 deletes it.
5. **The agent rejects action types it has no graph for (422) instead of queueing them**, and `app` rejects the ones it cannot assemble a context for. The three Phase 3 actions therefore fail fast at the API instead of failing in a worker.
6. **Dispatch failures are recorded, not swallowed**: a broker or agent outage marks the action `failed` with the reason and returns 503, so a promoter who clicked and got nothing sees why. Conversely, polling never fails because the agent is restarting — the last known state is returned.
7. **`ActionType`/`ActionStatus` moved out of `mentoring/domain/student.py` into `mentoring/domain/action.py`**, next to the new `AgentAction` entity, now that actions are real rather than a table waiting to be used.
8. **Ruff in `agent` fixed on the way in** (36 errors → 0), since the phase touched most of that service anyway; prompt-text files get a scoped `E501` exemption because rewrapping a line there changes the prompt. Pyright in `agent/src` is down to the single pre-existing pydantic-settings pattern, and every new module in `app/src/mentoring` is pyright-clean.

**Phase 3 — the rest of the catalog, thesis versions, and the end of the transitional endpoints** — ✅ **done 2026-09-06**. The action catalog is complete, students have uploaded thesis versions, and nothing pre-mentoring is left in the code.

**A sixth action was added on the user's request: `defence_questions`** — three questions a defence committee would ask, one each on the research problem, the method, and the conclusions, drawn from the uploaded thesis. It is the only action aimed at the defence rather than at improving the draft, and it needs no acceptance: the promoter reads it and takes it to the defence.

Actions now: `propose_topic`, `evaluate_methodology`, `check_progress`, `draft_meeting_note`, `defence_questions`, `generate_review`.

Verified against the running stack with the real model, not only in tests: a DOCX thesis (regression on institutions and growth) was uploaded and parsed in-process; `defence_questions` returned three questions that visibly used the work — sample selection, and the interpretation of significance given a short 2004-2022 series; `check_progress` on a student with one version returned 409 with a message saying why; `draft_meeting_note` turned "omówiliśmy rozdział 2, student poprawi dobór próby, termin 20.03" into a clean note, and accepting it created a real `meeting_notes` row carrying `source_action_id`. The frontend was rebuilt as a production image and serves the new routes. Smoke data deleted afterwards.

Decisions worth recording:

1. **The graph dispatcher covers every `ActionType`, and `IMPLEMENTED_ACTIONS` is now `frozenset(ActionType)`.** Five of the six are one-node graphs; only `generate_review` runs the four-node pipeline. Adding an action is a node plus a prompt plus a context builder — no new state schema, no new task, no new endpoint.
2. **Guidelines are loaded by `agent`, not shipped by `app`.** The requirements document is static data the agent owns (files today, pgvector in Phase 5), so `tasks.py` injects it for the two actions judged against requirements. `app` sends `thesis_type` and nothing more.
3. **"Not enough data" is a 409, not a 422 or a queued job that fails.** `MissingContextError` covers defence questions without a thesis, a progress check with one version, and a note-drafting action with nothing to write up; the message says what is missing.
4. **Accepting is per action.** A topic proposal sets `current_topic`; an accepted note becomes a `meeting_notes` row with `source_action_id` set, so an AI-drafted note stays distinguishable from a typed one forever. The other four are read-only advice and accepting them only records that the promoter read them.
5. **Context assembly fetches only what its action needs** — `check_progress` reads exactly two draft rows, `propose_topic` reads none — and records provenance as IDs (`draft_ids`, `note_ids`) in `input_ref`, never the text.
6. **The extracted text never travels back out.** A draft response carries version, filename, page count, character count and a 400-character preview; the thesis itself stays in the row.
7. **Transitional code is gone as planned**: `POST /extract`, the `/analysis/*` proxy and `src/proxy/` in `app`; `POST/GET /analysis`, the `analyze_thesis` task and the `evaluation_id` column (migration `0003_drop_legacy`) in `agent`. `app`'s health endpoint moved to `src/shared/health.py`, since "proxy" no longer describes anything.
8. **One JSON helper for every node** (`agent/src/application/json_output.py`): four copies of "strip the markdown fence, tolerate list content, parse" existed before the three new nodes would have made seven.
9. **Frontend rewritten around students** — `/students` and `/students/[id]` (topic, versions, notes, actions with polling and accept), `useAnalysis` → `useAction`, `GATEWAY_URL`/`PARSER_URL` → one `APP_URL`, and one `lib/appProxy.ts` behind every route handler so a refusal's own explanation reaches the UI. The old `/analysis` pages were deleted with the endpoints they called; `AnalysisResult` survives as the renderer for the two findings-based actions.

**Phase 4 — BYOK wiring** — ✅ **done 2026-09-06**. Built as the § above describes: the key stops being an inert admin field and becomes the thing that decides whose account an action runs on.

Verified against the running stack, including the case that matters: a **promoter** (not an admin) stored a Claude key and triggered `propose_topic`; the run went to Anthropic and came back `failed` with *"API key is invalid"* — the deliberately fake key proves the call really left on that account rather than quietly falling back. Removing the key and re-running the same action completed on the self-hosted model with three topics. The stored column holds a Fernet token (`gAAAAAB…`, no plaintext), and neither `agent_actions.output`, `error` nor `input_ref` contains the key.

Decisions worth recording:

1. **The key lives in a ContextVar for the duration of one task, not in the graph state.** State is what `_result_payload` serialises and what LangGraph would checkpoint; a key placed there is a key one whitelist change away from being persisted. `use_credentials()` sets it around the graph run and resets it in a `finally`, so a prefork worker cannot hand one promoter's key to the next task. Nodes still call `get_llm()` and know nothing about any of it.
2. **The key travels as its own Celery argument**, never inside `context` — same reasoning one level up: `context` becomes state.
3. **`model` applies only to the self-hosted path.** It names an Ollama tag; handing `qwen3:30b-a3b` to Anthropic would just fail, so BYOK runs use a per-provider default (`claude-sonnet-4-20250514`, `gpt-4o`). Choosing between a provider's models is not wired — noted as debt.
4. **A key that cannot be used is treated as absent, not as an error**: no provider stored (rows from before this phase), or an undecryptable token after a `FERNET_KEY` rotation. The action still runs, on the self-hosted model, and the reason is logged.
5. **`PATCH /settings/api-key` is any authenticated user**, and gained `DELETE` — a key you cannot remove is a key you cannot rotate. The provider is validated against the same two-provider list the agent enforces.
6. **The UI moved from the admin panel to the profile page**, which is what "bring your own key" means: it shows whether a key is stored and for which provider, never the key itself.

**Phase 5 — pgvector RAG for guidelines** — ✅ **done 2026-09-06**. The requirements documents stop being pasted whole into every prompt: they are split into their own numbered sections, embedded, and retrieved against the thesis in front of the model. Files stay the source of truth on disk; `analysis.guideline_chunks` holds the retrievable copy.

Decisions worth recording:

1. **Postgres 16 keeps its Alpine base; pgvector is compiled against it** (`infra/postgres/Dockerfile`). Switching to the official Debian `pgvector/pgvector:pg16` image would have pointed a glibc build at a musl-built data directory — a collation-provider change under a live volume, which is how text indexes quietly go wrong. Alpine's own `postgresql-pgvector` package builds against PG 18 and drops `vector.so` in a path this server never reads.
2. **The embedding column has no fixed dimension.** The embedding model is a setting; pinning 768 into the schema would make swapping models a migration. Every row records the model and width that produced it, and retrieval filters on the model in use, so vectors from two models can coexist and never mix. At tens of chunks per thesis type an exact scan beats an approximate index anyway — add HNSW, and a fixed dimension with it, when the corpus stops being small.
3. **Chunks follow the document's own `##` sections, not a character count.** These are numbered rules; a rule cut in half retrieves as nonsense and cannot be cited back.
4. **Some sections are always included.** A normative document loses its meaning if retrieval drops the part that defines the judgement: pull three sections about structure, leave out §4 *Severity Classification*, and every finding becomes a guess at what "critical" means here. Sections matching severity/classification/scoring are pinned at ingestion and returned whatever the distances say; the rest are the nearest `RAG_TOP_K`. Results come back in document order, so the prompt reads like the document rather than like a ranking.
5. **Retrieval degrades to the file, never to nothing.** No ingestion run, no embedding model pulled, an unreachable Ollama, a database blip — all end with the whole requirements document, which is exactly what every action had before this phase. Nothing about this phase can fail an action.
6. **Embeddings are self-hosted only**, deliberately: they run over the university's requirements *and* over the student's unpublished thesis, which is the material the local-first default exists to keep local. A user's own key pays for the review, not for indexing a thesis.
7. **Ingestion is an idempotent script** (`agent/scripts/ingest_guidelines.py`, `make ingest-guidelines`), not a startup hook: re-running it replaces one model's chunks for one thesis type and leaves other models' rows alone.

Verification: the extension (`vector 0.8.0`) and the table are live on the existing volume, with the previous data intact; the search path — the `vector` column, `<=>`, pinning, model isolation, document ordering — was exercised against the real database, and the fallback was too (it logs `guideline_embedding_failed` and hands over the whole document).

**Turned on afterwards, on request**, and it changed two things about the design:

1. **Embeddings needed their own base URL.** This deployment runs chat models on a server that answers `501 … start it with --embeddings`, while the Ollama the stack ships serves them happily. `EMBEDDING_BASE_URL` (default `http://ollama:11434`) is now separate from `OLLAMA_BASE_URL` — a chat server is not obliged to do embeddings, and conflating the two hid that.
2. **The chunks were too coarse to retrieve anything.** With `nomic-embed-text` ingested, the first live retrieval returned **99% of the document**: each requirements file has four `##` sections, so "the nearest four" is the whole file. Sections longer than 900 characters are now split by their `###` subsections — each carrying its parent heading, so a retrieved rule is still citable — while the pinned severity section is never split, because half a rulebook is worse than none. That took the documents from 5 chunks to 14 and 18, and `RAG_TOP_K` from 4 to 6. Retrieval now returns 44–65% depending on the query: a formatting question pulls §2 and its length/citation/language subsections, a bibliography question pulls §1.7, and §4 *Severity* is pinned into every one of them.

Worth being plain about: at 4-6 kB per document this is scaffolding, not a saving. Its value is the shape it puts in place for promoter-specific guidelines and more thesis types — and the fact that it now demonstrably retrieves *differently* for different theses instead of pasting the same file every time.

**Phase 6 — deploy/CI groundwork** — ✅ **done 2026-09-06**. `.github/workflows/ci.yml`, `.pre-commit-config.yaml`, `infra/jenkins/Jenkinsfile` and `infra/sonarqube/sonar-project.properties` all exist for the first time; `docs/sessions.md` §5.2/5.3 described them for months and none of it had been written.

Decisions worth recording:

1. **The type gate was made real before it was enforced.** `pyright --strict` had never passed on this codebase (736 errors in the old `identity`, 160 in `app` after consolidation). The last four errors in production code — an untyped `call_next` in `app`'s middleware, and pydantic-settings' env-populated constructor in both services — were fixed here, so **`pyright src` is now clean in both services** and CI checks it on every PR. The ~250 remaining errors all sit in test files (`TestClient`/`httpx` unknowns) and stay documented debt rather than a suppressed gate.
2. **A fifth job: migrations against an empty database.** Every phase so far upgraded a database that already existed; nothing had ever built the schema from zero, which is exactly what a first deploy does. The job runs all three lineages on `pgvector/pgvector:pg16` — the plain postgres image would pass CI and then fail on deploy at `CREATE EXTENSION vector`. Verified locally on a throwaway container: three schemas, eleven tables, from nothing.
3. **Jenkins builds, migrates, then deploys** — migrations run before the new containers serve traffic, and the production `.env` comes from a Jenkins credential, is written for the build and deleted in `post { always }`. Images are built on the host rather than pulled: there is no registry yet, and choosing one was explicitly left open by this plan.
4. **Sonar is skipped, not failed, without a token.** The server is self-hosted; a fork or a fresh clone has no `SONAR_TOKEN`, and a red X on every such build teaches people to ignore red X's.
5. **Pre-commit deliberately runs neither `pytest` nor `pyright`.** The app suite takes ~55 s by design (bcrypt), and a type-check needs each service's whole venv. Hooks that slow get bypassed with `--no-verify`, and then nothing runs at all; both belong in CI, which is where they now are. The hooks are `ruff --fix`, eslint, and file hygiene including `detect-private-key`.
6. **`ruff format` is still not enabled.** It would reformat ~30 existing files in one pass; that is worth doing as its own change, not folded into the commit that introduces CI. Noted as debt, same as the `fastapi`/`starlette` pins.

Verification: `uvx pre-commit run --all-files` passes on the whole repository; every command the workflow runs was executed locally (both services `uv sync --frozen`, `ruff`, `pyright src`, `pytest`; the frontend's lint, typecheck and tests); and the migration chain was applied to an empty pgvector database exactly as the `migrations` job does it.

---

## Verification summary

Each phase lists its own tests above; overall gate before moving to the next phase: `uv run pytest -v --cov=src` (≥80%) + `ruff check` + `pyright` clean in the touched service(s), plus one manual end-to-end smoke test through `docker compose up`. No phase is "done" on unit tests alone given how much of this plan is cross-service wiring.
