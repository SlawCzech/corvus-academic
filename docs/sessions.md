# Corvus — plan sesji Claude Code

> Używaj tego pliku jako przewodnika przez każdą fazę.
> Po każdej sesji aktualizuj sekcję "Stan projektu" na końcu.

---

## Szablon na start każdej sesji

Wklej to jako pierwszy prompt w nowej sesji Claude Code:

```
Read CLAUDE.md.

Project state: [what was done in the previous session]
Last commit: [short description]

Next step: [session name from the plan below]

[paste session prompt]
```

---

## Faza 1 — rdzeń AI (tydzień 1–2)

### Sesja 1.1 — setup projektu ✅
```
Read CLAUDE.md.

Initialize project Corvus using uv as package manager.
Create directory structure:
agent/src/{domain,application,infrastructure} and agent/tests/domain/.

Run: uv python pin 3.12

Configure pyproject.toml with:
- requires-python = ">=3.12,<3.14"
- [build-system] hatchling
- [tool.ruff.lint] line-length=88,
  select=["E","F","I","N","UP","ANN","S","B"]
- [tool.ruff.lint.per-file-ignores] "tests/**/*.py" = ["S101"]
- [tool.pyright] pythonVersion="3.12", typeCheckingMode="strict"
- [tool.pytest.ini_options] asyncio_mode="auto"
- [tool.coverage.report] fail_under=80

Add dependencies via uv add:
- prod: fastapi pydantic structlog langchain langgraph langchain-anthropic
- dev: pytest pytest-asyncio pytest-cov ruff pyright

Add .env.example with: MODEL_BACKEND, ANTHROPIC_API_KEY,
LANGCHAIN_TRACING_V2, LANGCHAIN_API_KEY, LANGCHAIN_PROJECT,
REDIS_URL, DATABASE_URL, FERNET_KEY, JWT_SECRET.

Add .gitignore ignoring: .env, __pycache__, .venv, .pyright,
.ruff_cache, dist/, .uv/, .claude/.

Verification: uv run ruff check . and uv run pyright
must pass with no errors.
```

---

### Sesja 1.2 — encje domenowe ✅
```
Read CLAUDE.md.

Create domain entities in agent/src/domain/.

metadata.py — Value Object:
  ThesisMetadata(frozen=True): author: str, title: str,
  year: int, field_of_study: str

analysis.py — Entities:
  FindingSeverity(StrEnum): CRITICAL, MAJOR, MINOR
  Finding(frozen=True): section: str, description: str,
    severity: FindingSeverity, suggestion: str
  ThesisAnalysis: thesis_id: UUID, findings: list[Finding],
    requirements: list[str]
    methods: critical_count() -> int,
             is_ready_to_submit() -> bool

review.py — Entities:
  Score(frozen=True): criteria: str, points: int, max_points: int
    method: percentage() -> float
  Review(frozen=True): review_id: UUID, thesis_id: UUID,
    scores: list[Score], summary: str, recommendation: str
    method: total_percentage() -> float

evaluation.py — Aggregate Root:
  EvaluationStatus(StrEnum): UPLOADED, ANALYZING, ANALYZED,
    REVIEWED, REJECTED
  VALID_TRANSITIONS: dict[EvaluationStatus, set[EvaluationStatus]]:
    UPLOADED  → {ANALYZING}
    ANALYZING → {ANALYZED, REJECTED}
    ANALYZED  → {REVIEWED}
    REVIEWED  → set()
    REJECTED  → set()
  ThesisEvaluation (Aggregate Root):
    id: UUID, metadata: ThesisMetadata,
    status: EvaluationStatus = UPLOADED,
    analysis: ThesisAnalysis | None = None,
    review: Review | None = None
    private methods: _transition(target: EvaluationStatus) -> None
    public methods:
      start_analysis() -> None
      complete_analysis(analysis: ThesisAnalysis) -> None
        (sets ANALYZED or REJECTED via is_ready_to_submit())
      attach_review(review: Review) -> None
      is_complete() -> bool

Rules:
- StrEnum imported from enum (stdlib, Python 3.11+)
- UUID imported from stdlib uuid module, passed in from outside —
  entities never generate their own UUID
- No imports from FastAPI, LangChain, SQLAlchemy or any framework
- Full type hints everywhere
- All comments and docstrings in English
- Each class has a one-sentence docstring

Write tests in agent/tests/domain/ covering:
- all valid state transitions
- invalid transitions raise ValueError with descriptive message
- is_ready_to_submit() with and without CRITICAL findings
- percentage() and total_percentage() edge cases (zero max_points)
- ThesisMetadata is frozen (attempted mutation raises TypeError)
- complete_analysis() correctly routes to ANALYZED vs REJECTED

Verification: uv run pytest agent/tests/domain/ -v
and uv run ruff check . and uv run pyright must pass with no errors.
```

---

### Sesja 1.3 — AnalysisState + pierwszy węzeł LangGraph
```
Read CLAUDE.md.

Project state: session 1.2 complete — domain entities in
agent/src/domain/ (ThesisMetadata, Finding, ThesisAnalysis,
Score, Review, ThesisEvaluation with state machine).
FindingSeverity uses StrEnum; EvaluationStatus uses plain Enum
(serialized to str via .value at the graph boundary).
All tests pass, ruff and pyright clean.

--- AnalysisState ---

Create agent/src/application/state.py:

  class ThesisMetadataDict(TypedDict):
      author: str
      title: str
      year: int
      field_of_study: str

  class AnalysisState(TypedDict):
      evaluation_id: str             # UUID serialized as str for LangGraph
      metadata:      ThesisMetadataDict  # ThesisMetadata serialized at boundary
      text:          str             # extracted thesis text from parser
      guidelines:    str             # university + promoter guidelines
      findings:      list[Finding]   # grows across nodes 1-3
      scores:        list[Score]     # filled by generate_review node
      review:        Review | None   # filled by generate_review node
      status:        str             # EvaluationStatus.value (plain Enum)
      error:         str | None      # set on exception, None otherwise

  Note: ThesisMetadata → ThesisMetadataDict and EvaluationStatus → str
  happen at the graph boundary. Conversion in application layer, not domain.

--- llm_factory placeholder ---

Create agent/src/infrastructure/llm_factory.py:
  - function get_llm() -> BaseChatModel
  - returns ChatAnthropic(model="claude-sonnet-4-20250514")
    with api_key loaded from settings via pydantic-settings
  - this is a placeholder — full model selector comes in session 2.3

Create agent/src/infrastructure/settings.py:
  - class Settings(BaseSettings) with fields:
    anthropic_api_key: str
    langchain_tracing_v2: bool = False
    langchain_project: str = "corvus"
  - loaded from .env automatically

--- analyze_structure node ---

Create agent/src/application/nodes/structure.py:
  - function analyze_structure(state: AnalysisState) -> AnalysisState
  - calls get_llm() to obtain the model
  - system prompt: you are a thesis reviewer analyzing chapter
    structure and coherence of a diploma thesis
  - user prompt: combines state["text"] and state["guidelines"]
  - expects model to return a structured list of structural findings
  - parses response into list[Finding] with severity from FindingSeverity
  - returns state with state["findings"] extended by structural findings
  - on any exception: sets state["error"] = str(exception),
    leaves findings unchanged, returns state
  - all log messages via structlog, not print()

Add to .env.example:
  LANGCHAIN_TRACING_V2=true
  LANGCHAIN_PROJECT=corvus

--- Tests ---

Create agent/tests/test_application/test_structure_node.py:

  Test 1 — happy path:
  - patch get_llm at src.application.nodes.structure.get_llm
  - mock returns AIMessage with a plausible structured response
  - call analyze_structure(state) with sample state
  - assert len(result["findings"]) > 0
  - assert result["error"] is None

  Test 2 — API error:
  - patch get_llm, mock raises Exception("API timeout")
  - call analyze_structure(state)
  - assert result["error"] is not None
  - assert result["findings"] == []

  Test 3 — state passthrough:
  - existing findings in state must be preserved (not replaced)
  - new findings are appended, not overwritten

Rules:
- No imports from domain layer in tests — use dict literals
  for AnalysisState construction
- All comments and docstrings in English
- No real API calls in tests — always mock get_llm

Verification: run from agent/ — uv run pytest tests/ -v
and uv run ruff check . and uv run pyright must pass with no errors.
```

---

### Sesja 1.4 — graf LangGraph
```
Read CLAUDE.md.

Project state: session 1.3 complete — AnalysisState TypedDict
(with ThesisMetadataDict for metadata), analyze_structure node
with 3 tests, llm_factory placeholder (ChatAnthropic),
Settings via pydantic-settings. FindingSeverity is StrEnum;
EvaluationStatus is plain Enum — serialized as .value in state.
All tests pass, ruff and pyright clean.

--- Stub nodes ---

Create these three files (each returns state unchanged):
  agent/src/application/nodes/methodology.py
    def analyze_methodology(state: AnalysisState) -> AnalysisState
  agent/src/application/nodes/requirements.py
    def check_requirements(state: AnalysisState) -> AnalysisState
  agent/src/application/nodes/review.py
    def generate_review(state: AnalysisState) -> AnalysisState

Each stub has a one-sentence docstring and logs via structlog.

--- Graph ---

Create agent/src/application/graph.py:
  from langgraph.graph import StateGraph, START, END
  from langgraph.graph.state import CompiledStateGraph

  - StateGraph(AnalysisState) with four nodes:
      "analyze_structure"   → src.application.nodes.structure
      "analyze_methodology" → src.application.nodes.methodology
      "check_requirements"  → src.application.nodes.requirements
      "generate_review"     → src.application.nodes.review
  - edges: START → analyze_structure → analyze_methodology
           → check_requirements → generate_review → END
  - function build_analysis_graph() -> CompiledStateGraph

--- Tests ---

Create agent/tests/test_application/test_graph.py.
Patch all four node functions inside src.application.graph
(that is where the graph imports them):
  patch("src.application.graph.analyze_structure", ...)
  patch("src.application.graph.analyze_methodology", ...)
  etc.

Each mock must accept state and return it unchanged so the graph
can pass state through: side_effect = lambda s: s

  Test 1 — all nodes called:
  - invoke graph with a minimal valid AnalysisState dict
  - assert each of the four mocks was called exactly once

  Test 2 — node order:
  - use a shared call_log list; each mock appends its name via
    side_effect before returning state
  - assert call_log == ["analyze_structure", "analyze_methodology",
                        "check_requirements", "generate_review"]

  Test 3 — return shape:
  - invoke graph with minimal state (all required keys present,
    findings=[], scores=[], review=None, error=None)
  - assert result is a dict containing all nine AnalysisState keys

  Test 4 — no short-circuit on error:
  - set analyze_structure mock to set state["error"] = "boom"
    and return that state
  - assert remaining three nodes are still called

Rules:
- Construct AnalysisState input as a plain dict (cast if needed)
- No real LLM calls — nodes are fully mocked
- All comments and docstrings in English

Verification: run from agent/ — uv run pytest tests/ -v --tb=short
and uv run ruff check . and uv run pyright must pass with no errors.
```

---

## Faza 2 — dokument i kolejkowanie (tydzień 3–4)

### Sesja 2.1 — serwis parser
```
Read CLAUDE.md.

Project state: phase 1 complete — LangGraph graph with 4 nodes
(1 implemented, 3 stubs), all tests pass.

Create microservice parser/ with FastAPI:
- parser/src/domain/document.py:
    Document(frozen=True): text: str, pages: int, format: str
- parser/src/application/extractor.py:
    extract_pdf(file: bytes) -> Document  via PyMuPDF (fitz)
    extract_docx(file: bytes) -> Document via python-docx
- parser/src/infrastructure/router.py: FastAPI router,
    POST /extract — accepts UploadFile,
    returns {"text": str, "pages": int, "format": str}
    422 for unsupported format, 500 for extraction error
    all errors logged via structlog
- parser/main.py: FastAPI app with router and GET /health
- parser/pyproject.toml: separate uv project, Python 3.12,
    deps: fastapi, uvicorn, pymupdf, python-docx, structlog

Create parser/tests/fixtures/ with test.pdf and test.docx
generated in conftest.py via fpdf2 and python-docx.

Write tests:
- parser/tests/test_extractor.py — unit tests for extract_pdf
  and extract_docx with fixture files
- parser/tests/test_router.py — integration tests with TestClient

Verification: uv run pytest parser/tests/ -v
and uv run ruff check parser/ and uv run pyright parser/
must pass with no errors.
```

---

### Sesja 2.2 — Celery + Redis
```
Read CLAUDE.md.

Project state: session 2.1 complete — parser microservice
with passing tests.

Add to agent/: uv add celery redis

Create agent/src/application/tasks.py:
  @shared_task(bind=True, max_retries=3, default_retry_delay=60)
  def analyze_thesis(self, evaluation_id: str, text: str,
                     guidelines: str, metadata: dict) -> dict:
    - builds initial AnalysisState from parameters
    - calls build_analysis_graph().invoke(state)
    - on exception: raise self.retry(exc=exc)
    - returns result dict

Create agent/src/infrastructure/celery_app.py:
  - Celery config via pydantic-settings (REDIS_URL from env)
  - broker_url and result_backend pointing to Redis
  - task_serializer="json", accept_content=["json"]

Write agent/tests/application/test_tasks.py:
  - mock build_analysis_graph and Redis
  - verify task calls graph with correct arguments
  - verify retry is triggered on exception

Verification: uv run pytest agent/tests/ -v
and uv run ruff check agent/ and uv run pyright agent/
must pass with no errors.
```

---

### Sesja 2.3 — model selector + pozostałe węzły
```
Read CLAUDE.md.

Project state: session 2.2 complete — Celery with Redis,
analyze_thesis task with retry.

Replace placeholder in agent/src/infrastructure/llm_factory.py:
  def get_llm() -> BaseChatModel:
    match settings.model_backend:
      case "claude" → ChatAnthropic(model="claude-sonnet-4-20250514")
      case "ollama" → ChatOllama(model=settings.ollama_model,
                                 base_url=settings.ollama_base_url)
      case "openai" → ChatOpenAI(model="gpt-4o")
      case _        → raise ValueError(f"Unknown MODEL_BACKEND: ...")

Add to Settings: model_backend: str, ollama_model: str,
ollama_base_url: str.

Implement remaining 3 nodes (replace stubs):
  - analyze_methodology: checks methodology and bibliography
  - check_requirements: checks conformance with guidelines
    (no real RAG yet — use guidelines from state directly)
  - generate_review: produces Review with Score per criterion,
    calls complete_analysis() on ThesisEvaluation to route
    status to ANALYZED or REJECTED

Write parametrized tests for llm_factory:
  @pytest.mark.parametrize("backend", ["claude","ollama","openai"])
  with mocks for each variant.

Write tests for each new node.

Verification: uv run pytest agent/tests/ -v --cov=agent/src
and uv run ruff check agent/ and uv run pyright agent/
must pass with no errors. Coverage >= 80%.
```

---

## Faza 3 — API i baza (tydzień 5–6)

### Sesja 3.1 — gateway + auth
```
Read CLAUDE.md.

Project state: phase 2 complete — parser, Celery, model selector,
all 4 LangGraph nodes implemented.

Create microservice gateway/ with FastAPI:
- gateway/src/domain/user.py:
    Role(StrEnum): ADMIN, PROMOTOR
    User(frozen=True): id: UUID, email: str, role: Role
- gateway/src/application/auth.py:
    create_token(user: User) -> str
    verify_token(token: str) -> User
    using python-jose and JWT_SECRET from env
- gateway/src/infrastructure/router.py:
    POST /auth/login  → {"access_token": str, "token_type": "bearer"}
    POST /analysis    → {"task_id": str} (auth required, sends to Celery)
    GET  /analysis/{task_id} → {"status": str, "result": dict | None}
    GET  /health      → {"status": "ok"}
    Dependency: get_current_user via Bearer token
- gateway/pyproject.toml: fastapi, uvicorn, python-jose,
    celery, redis, pydantic-settings, structlog

Write tests with TestClient mocking Celery:
- login with correct and incorrect credentials
- protected endpoints with and without token
- task status endpoint

Verification: uv run pytest gateway/tests/ -v
and uv run ruff check gateway/ and uv run pyright gateway/
must pass with no errors.
```

---

### Sesja 3.2 — Postgres + Alembic
```
Read CLAUDE.md.

Project state: session 3.1 complete — gateway with JWT auth
and endpoints.

Add to gateway/ and agent/: uv add sqlalchemy asyncpg alembic

Create gateway/src/infrastructure/models.py (SQLAlchemy 2.0):
  UserModel:     id (UUID PK), email, role, hashed_password, created_at
  AnalysisModel: id (UUID PK), evaluation_id, user_id (FK),
                 status, result (JSON), created_at, updated_at

Create gateway/src/infrastructure/repositories.py:
  AnalysisRepository: async save() and async find_by_id()
  UserRepository:     async find_by_email()

Initialize Alembic: alembic init gateway/alembic
Create first migration: alembic revision --autogenerate
  -m "initial schema"

Write integration tests with pytest-asyncio using
in-memory SQLite (sqlite+aiosqlite:///:memory:):
- save and retrieve Analysis
- save and retrieve User

Verification: uv run pytest gateway/tests/ -v
and uv run ruff check gateway/ and uv run pyright gateway/
must pass with no errors.
```

---

### Sesja 3.3 — secret vault
```
Read CLAUDE.md.

Project state: session 3.2 complete — Postgres with Alembic,
async repositories.

Create gateway/src/infrastructure/secrets.py:
  class SecretService:
    __init__(self, key: bytes) -> None
    encrypt(plain: str) -> str  via cryptography.fernet.Fernet
    decrypt(token: str) -> str
    FERNET_KEY loaded from env via pydantic-settings

Add to UserModel: api_key_encrypted: str | None

Add to gateway/src/infrastructure/router.py:
  PATCH /settings/api-key  (ADMIN only):
    accepts {"api_key": str, "provider": str},
    encrypts and saves to DB
  GET /settings/api-key/status:
    returns {"configured": bool} — never exposes plain key

Write tests:
- encrypt/decrypt roundtrip with fixture key
- endpoint never returns plain text key
- ADMIN can set key, PROMOTOR cannot

Verification: uv run pytest gateway/tests/ -v --cov=gateway/src
and uv run ruff check gateway/ and uv run pyright gateway/
must pass with no errors. Coverage >= 80%.
```

---

## Faza 4 — frontend (tydzień 7–8)

### Sesja 4.1 — setup Next.js + upload
```
Read CLAUDE.md.

Project state: phase 3 complete — gateway with auth,
Postgres, secret vault.

Create frontend/ with Next.js App Router and strict TypeScript:
  npx create-next-app@latest frontend --typescript --app
    --tailwind --eslint --no-src-dir
  configure tsconfig.json: strict: true
  add: npm install vitest @testing-library/react
    @testing-library/user-event react-dropzone swr zod react-hook-form

Generate API types from gateway OpenAPI schema:
  npm install -D openapi-typescript
  add script: "gen-types": "openapi-typescript
    http://localhost:8000/openapi.json -o lib/api.types.ts"

Create page /analysis:
  - FileUpload component (react-dropzone): PDF and DOCX only,
    max 50MB, shows filename and size
  - useAnalysis hook: POST /analysis → task_id,
    polls GET /analysis/{task_id} every 3s via useSWR,
    stops polling when status === "done" or "error"
  - AnalysisResult component: findings grouped by severity,
    scores as progress bars, summary and recommendation

Write Vitest + Testing Library tests:
  - FileUpload: accepts correct formats, rejects others
  - useAnalysis: polling stops at "done"
  - AnalysisResult: renders findings and scores

Verification: npm run typecheck and npm test and npm run lint
must pass with no errors.
```

---

### Sesja 4.2 — panel admina + logowanie
```
Read CLAUDE.md.

Project state: session 4.1 complete — /analysis page
with upload, polling and results display.

Create page /login:
  - form (React Hook Form + Zod): email, password
  - validation: valid email format, password min 8 chars
  - calls POST /auth/login, stores token in httpOnly cookie
    via Next.js API route (not localStorage)
  - redirects to /analysis on success

Create page /admin (protected — redirect to /login
if no token or role !== ADMIN):
  - section "AI Model": radio LOCAL/CLOUD,
    API key field (type="password" with visibility toggle),
    save button → PATCH /settings/api-key
  - section "Guidelines": PDF dropzone,
    list of uploaded files with date
  - section "Users": table of promoters

Next.js middleware to protect /admin and /analysis
(checks cookie token).

Write tests:
  - login form: validation, submit, redirect
  - /admin: redirect when no token
  - API key section: visibility toggle, submit

Verification: npm run typecheck and npm test and npm run lint
must pass with no errors.
```

---

## Faza 5 — CI/CD i jakość (tydzień 9–10)

### Sesja 5.1 — docker-compose
```
Read CLAUDE.md.

Project state: phase 4 complete — frontend with login,
upload and admin panel.

Create infra/docker-compose.yml with all services:
  frontend:   build ./frontend,  port 3000, depends_on gateway
  gateway:    build ./gateway,   port 8000, env_file .env,
              depends_on postgres redis, healthcheck GET /health
  parser:     build ./parser,    port 8001, healthcheck GET /health
  agent:      build ./agent,     command: celery worker,
              env_file .env, depends_on redis postgres ollama
  flower:     image mher/flower, port 5555, depends_on redis
  ollama:     image ollama/ollama, port 11434, volumes ollama_data
  redis:      image redis:7-alpine, port 6379,
              healthcheck redis-cli ping
  postgres:   image postgres:16-alpine, port 5432,
              volumes postgres_data, healthcheck pg_isready
  jenkins:    image jenkins/jenkins:lts, port 8080,
              volumes jenkins_data
  sonarqube:  image sonarqube:community, port 9000,
              volumes sonarqube_data

Create Dockerfile for each Python service:
  - multi-stage: builder (uv sync) + runtime (no dev deps)
  - non-root user
  - HEALTHCHECK instruction

Create infra/docker-compose.override.yml for local dev:
  - mounted volumes for hot-reload
  - DEBUG=true

Verification: docker-compose config passes with no errors,
docker-compose up --build starts all services.
```

---

### Sesja 5.2 — GitHub Actions + pre-commit
```
Read CLAUDE.md.

Project state: session 5.1 complete — docker-compose
with all services.

Create .github/workflows/ci.yml:
  trigger: push and pull_request on main and develop
  job test-gateway:   uv run pytest + ruff check + pyright
  job test-parser:    same for parser/
  job test-agent:     same for agent/
  job test-frontend:  npm ci + typecheck + vitest
  job sonarqube:      SonarSource/sonarqube-scan-action@v2
    needs: [test-gateway, test-parser, test-agent, test-frontend]
    secrets: SONAR_TOKEN, SONAR_HOST_URL

Create .github/workflows/cd.yml:
  trigger: push on main (after PR merge)
  build and push Docker images to GHCR
  SSH to server: docker-compose pull + up -d

Create .pre-commit-config.yaml:
  - ruff check and ruff format for Python
  - prettier for TypeScript/JSON
  - pyright for Python
  - check-added-large-files (max 1MB)
  - detect-private-key

Create infra/sonarqube/sonar-project.properties.

Verification: pre-commit run --all-files passes with no errors.
```

---

### Sesja 5.3 — Jenkinsfile + README
```
Read CLAUDE.md.

Project state: session 5.2 complete — GitHub Actions CI/CD,
pre-commit hooks.

Create infra/jenkins/Jenkinsfile with stages:
  1. Checkout
  2. Test Python  — uv run pytest per service, parallel
  3. Test TypeScript — npm ci + npm test in frontend/
  4. SonarQube    — sonar-scanner with coverage results
  5. Build images — docker build per service
  6. Push to GHCR — docker push (main branch only)
  7. Deploy       — SSH + docker-compose pull + up -d (main only)
  8. Healthcheck  — curl all /health endpoints
  9. Notify       — email on failure

Use Jenkins Credentials for:
  GITHUB_TOKEN (GHCR push)
  SSH_KEY      (server deploy)
  SONAR_TOKEN

Create README.md:
  - Corvus project description
  - requirements: Docker, uv, Node 26
  - local setup in 5 steps
  - service architecture table
  - environment variables table

Verification: Jenkinsfile syntax valid
(check via Jenkins Pipeline Linter).
```

---

## Stan projektu

> Aktualizuj tę sekcję po każdej sesji.

| Sesja | Status | Data | Notatka |
|---|---|---|---|
| 1.1 setup | ✅ | — | structure, pyproject.toml, uv, Python 3.12 |
| 1.2 entities | ✅ | 2026-05-24 | 4 domain files, 23 tests, 100% coverage. StrEnum for FindingSeverity and EvaluationStatus. ThesisEvaluation as Aggregate Root with state machine via VALID_TRANSITIONS. |
| 1.3 node | ✅ | 2026-05-24 | AnalysisState TypedDict, Settings via pydantic-settings, get_llm placeholder, analyze_structure node with structlog. 3 tests, 99.3% coverage. |
| 1.4 graph | ✅ | 2026-05-26 | 3 stub nodes, CompiledStateGraph pipeline, 4 graph tests. 30 tests total, 96.2% coverage. pyproject.toml: `reportMissingTypeStubs = false` only. Inline suppressions for LangGraph's `CachePolicy[Unknown]` (file-level in graph.py) and `Command[Unknown]` (per-line in test_graph.py). |
| 2.1 parser | ✅ | 2026-05-27 | parser/ microservice: Document entity, extract_pdf/extract_docx, FastAPI POST /extract + GET /health. 14 tests, 98.6% coverage. python-multipart added as required dep. |
| 2.2 Celery | ✅ | 2026-05-27 | celery_app.py + analyze_thesis task, 3 tests. celery-types added for pyright. In eager mode, self.retry() raises Retry (not MaxRetriesExceededError). 33 tests total, 96.65% coverage. |
| 2.3 models | ✅ | 2026-05-28 | Full model selector (claude/ollama/openai), 3 implemented nodes (methodology, requirements, review). generate_review uses ThesisEvaluation.complete_analysis() for ANALYZED/REJECTED routing. 51 tests, 100% coverage. |
| 3.1 gateway | ✅ | 2026-05-29 | gateway/ microservice: Role/User domain, JWT auth (python-jose), in-memory user store (bcrypt), Celery client, 4 endpoints. 18 tests, 94.4% coverage. passlib replaced by direct bcrypt (bcrypt 5.x incompatibility). |
| 3.2 Postgres | ✅ | 2026-05-30 | SQLAlchemy 2.0 models (UserModel, AnalysisModel), async repositories, Alembic init + initial migration. 24 tests, 95.98% coverage. JSONB with SQLite variant for cross-DB tests (aiosqlite in-memory). greenlet required for sqlalchemy[asyncio]. |
| 3.3 secrets | ✅ | 2026-05-30 | SecretService (Fernet), api_key_encrypted on UserModel, Alembic migration, PATCH /settings/api-key (ADMIN only) + GET /settings/api-key/status. 37 tests, 92.51% coverage. |
| 4.1 upload | ✅ | 2026-05-30 | Next.js 16 App Router, FileUpload (react-dropzone), useAnalysis hook (SWR polling), AnalysisResult component. Route handlers proxy to parser+gateway. 22 tests (vitest + Testing Library), typecheck and lint clean. |
| 4.2 admin | ✅ | 2026-05-30 | Login page (RHF + Zod + zodResolver), httpOnly cookie via API route, /admin page with AI Model/Guidelines/Users sections, Next.js middleware protecting /admin and /analysis. 39 tests, typecheck and lint clean. noValidate on form required to bypass jsdom's native HTML5 email validation in tests. |
| 5.1 Docker | ✅ | 2026-05-30 | infra/docker-compose.yml (10 services + migrate one-shot), docker-compose.override.yml (hot-reload), Dockerfiles for gateway/parser/agent (uv multi-stage, non-root) and frontend (Next.js standalone). .dockerignore for all 4 services. next.config.ts: output="standalone". /api/health route added to frontend. Default model: qwen3:30b-a3b. LANGCHAIN_TRACING_V2=false by default. docker compose config passes. |
| post-5.1 (a) landing page | ✅ | 2026-05-31 | Next.js landing page (`app/page.tsx`) dodana poza planem sesji 4.x. |
| post-5.1 (b) model selector v2 | ✅ | 2026-05-31 | Wybór modelu per-request (nie tylko przez env), tryb `mode="review_only"` (pomija węzły struktura/metodologia/wymogi i idzie prosto do recenzji), poprawki w węźle review. `graph.py`: `build_analysis_graph(mode=...)`. |
| post-5.1 (c) RAG wytycznych + ReviewTone | ✅ | 2026-06-02 — 2026-06-03 | `agent/src/application/guidelines.py` (loader wytycznych uczelnianych/promotora, `check_requirements` podpięty), `agent/prompts/` z promptami per węzeł, `ReviewTone` (StrEnum: auto/enthusiastic/commendable/positive/diplomatic/reserved/negative) z AUTO jako domyślnym. |
| post-5.1 (d) user management + historia analiz | ✅ | 2026-06-05 | Gateway: zarządzanie użytkownikami i historia analiz (przed ekstrakcją identity — kod ten later przeniesiony). Frontend: nawigacja, auth refresh flow, strony user management. |
| post-5.1 (e) hardening + rate limiting | ✅ | 2026-06-05 — 2026-06-06 | Rate limiting na `/auth/login` (najpierw slowapi, potem `fastapi-limiter`), hardening gateway pod produkcję (przed ekstrakcją identity). |
| post-5.1 (f) wybór języka recenzji | ✅ | 2026-06-06 | `language` (pl/en) dodany do `AnalysisRequest`/`AnalysisState`, przekazywany przez agent → gateway → frontend UI. |
| post-5.1 (g) **ekstrakcja `identity`** | ✅ | 2026-06-09 — 2026-06-10 | Duży refaktor architektury (poza pierwotnym planem CLAUDE.md — patrz [Zmiany względem pierwotnego planu](#zmiany-względem-pierwotnego-planu)): auth/users/role/permissions/secrets wydzielone z `gateway` do nowego serwisu `identity` (port 8003, własna baza + Alembic). `gateway` staje się czystym reverse proxy (`httpx.AsyncClient`, brak domain/infrastructure poza router+settings). `agent` dostaje własne HTTP API (`infrastructure/api/`) zamiast przyjmowania zadań wyłącznie przez gateway→Celery bezpośrednio. |
| post-5.1 (h) identity — testy i hardening | ✅ | 2026-06-14 | Testy proxy w gateway, poprawki parametrów proxy, `Permission` enum + uprawnienia per-rola, walidacja email przez `email-validator` w `identity/src/domain/user.py`. Stan na dziś: identity 61 testów/84.6% cov, gateway 17 testów/100% cov, agent 83 testy/94.8% cov, parser 14 testów/98.6% cov, frontend 39 testów. |
| 5.2 CI/CD | ⬜ | — | GitHub Actions (`ci.yml`) i pre-commit hooks z sekcji 5.2 pierwotnego planu — nie rozpoczęte. Musi zostać zaktualizowane o serwis `identity` (5 jobów zamiast 4). |
| 5.3 Jenkins | ⬜ | — | Jenkinsfile + README z sekcji 5.3 — nie rozpoczęte. Uwaga: `README.md` już istnieje (commit `36f4502`, 2026-06-09), ale bez treści opisanej w planie sesji 5.3 (wymaga weryfikacji zawartości). |

---

## Zmiany względem pierwotnego planu

| Sesja | Zmiana | Powód |
|---|---|---|
| 4.2 | `noValidate` na formularzu logowania | jsdom egzekwuje HTML5 constraint validation na `input[type="email"]` — blokuje zdarzenie `submit` zanim react-hook-form uruchomi walidację; `noValidate` wyłącza natywną walidację przeglądarki |
| 4.2 | Inline `zodResolver` zastąpiony `@hookform/resolvers` v5 | v5 obsługuje zarówno Zod v3 jak i v4 przez detekcję `_zod` na schemacie; nie wymaga własnej implementacji resolvera |
| 1.2 | `StrEnum` dla `FindingSeverity` (nie `EvaluationStatus`) | `FindingSeverity` serializuje się natywnie do str; `EvaluationStatus` pozostaje plain `Enum` — wymaga `.value` przy serializacji |
| 1.2 | `ThesisEvaluation` jako Aggregate Root zamiast `ThesisSubmission` | Lepsza nazwa domenowa — obiekt reprezentuje ewaluację pracy |
| 1.2 | `ThesisMetadata` jako osobny Value Object | Dane opisowe nie należą do `ThesisAnalysis` — separacja odpowiedzialności |
| 1.2 | State machine przez `VALID_TRANSITIONS` dict | Czysta domena bez zewnętrznych bibliotek, Pyright weryfikuje kompletność |
| 1.3 | `metadata: ThesisMetadataDict` zamiast `dict` | Precyzyjne typowanie pola metadata w `AnalysisState` — TypedDict zamiast opaque dict |
| 1.3 | `AnalysisState` rozszerzony o `metadata`, `status` | Wynika ze zmian w domenie — agregat ma metadane i status |
| 1.3 | `Settings` przez pydantic-settings | Spójna konfiguracja przez env w całym projekcie |
| Wszystkie | Prompty w języku angielskim | Spójność z kodem — komentarze i docstringi w English |
| 1.4 | Pyright suppressions inline zamiast globalnych w pyproject.toml | Szerokie wyłączenia (`reportUnknownMemberType` itp.) ukrywałyby błędy w kodzie projektu; zamiast tego: `reportMissingTypeStubs = false` globalnie + `# pyright: reportUnknownMemberType=false` na poziomie pliku graph.py + per-line ignore w structure.py i test_graph.py |
| 1.4 | `StateGraph[AnalysisState, None, Any, Any]` zamiast `StateGraph` bez type args | Explicit type args eliminują `reportMissingTypeArgument` bez wyłączania całej reguły; `Any` dla InputT/OutputT bo LangGraph nie eksponuje tych typów publicznie |
| 5.1 | Dodano serwis `migrate` (one-shot `alembic upgrade head`) | Bez niego gateway startuje bez schematu DB i każde żądanie do bazy kończy się błędem |
| 5.1 | `.dockerignore` dla każdego serwisu | Bez nich build context zawierał `.venv`, `node_modules`, `tests/`, pliki coverage — wolne buildy i większe obrazy |
| 5.1 | Endpoint `/api/health` w Next.js | Healthcheck w Dockerfile trafiał w nieistniejący URL — kontener był zawsze `unhealthy` |
| 5.1 | `LANGCHAIN_TRACING_V2=false` jako domyślna wartość | Przy `true` bez `LANGCHAIN_API_KEY` LangChain próbuje połączyć się z LangSmith i loguje błędy przy każdym wywołaniu LLM |
| 5.1 | Domyślny model zmieniony na `qwen3:30b-a3b` | Model `qwen3.6:14b` nie był pobrany lokalnie; `qwen3:30b-a3b` jest dostępny i lepszy jakościowo |
| post-5.1 | **`identity` wydzielone jako osobny mikroserwis** (nie część `gateway`, jak w CLAUDE.md sekcja 3.1/3.2) | Rozdzielenie odpowiedzialności — auth/users/role/permissions/secrets to osobny bounded context; `gateway` pozostaje cienką warstwą routingu i JWT, łatwiejszą do skalowania i testowania niezależnie |
| post-5.1 | `gateway` bez własnej bazy danych i domeny — czyste reverse proxy (`httpx.AsyncClient`) | Konsekwencja ekstrakcji `identity`; gateway nie potrzebuje już Postgres ani Alembic |
| post-5.1 | `agent` dostaje własne HTTP API (`infrastructure/api/`) zamiast być czystym Celery-consumerem | Gateway musi mieć dokąd proxować `/analysis/*` — agent obsługuje teraz zarówno przyjmowanie zadań (FastAPI) jak i ich wykonanie (Celery worker w osobnym kontenerze `agent-worker`, ten sam obraz) |
| post-5.1 | Model, tryb (`mode`), ton recenzji (`review_tone`) i język (`language`) przekazywane per-request zamiast tylko przez zmienne środowiskowe | Frontend pozwala użytkownikowi wybrać te parametry przy każdej analizie — env vars (`MODEL_BACKEND` itp.) pozostają jako fallback/domyślne wartości |

---

## Checklist przed każdym commitem

- [ ] `uv run ruff check .` — no errors
- [ ] `uv run pyright` — no errors
- [ ] `uv run pytest --cov` — all tests pass, coverage >= 80%
- [ ] no `.env` in staged files (`git status`)
- [ ] commit message: `feat:` / `fix:` / `test:` / `chore:` / `docs:` / `refactor:`
