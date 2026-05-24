# Corvus — plan sesji Claude Code

> Używaj tego pliku jako przewodnika przez każdą fazę.
> Po każdej sesji aktualizuj sekcję "Stan projektu" na końcu.

---

## Szablon na start każdej sesji

Wklej to jako pierwszy prompt w nowej sesji Claude Code:

```
Jesteśmy w projekcie Corvus. Przeczytaj CLAUDE.md.

Stan projektu: [co zostało zrobione w poprzedniej sesji]
Ostatni commit: [krótki opis]

Następny krok: [nazwa sesji z planu poniżej]

[wklej prompt sesji]
```

---

## Faza 1 — rdzeń AI (tydzień 1–2)

### Sesja 1.1 — setup projektu ✅
```
Jesteśmy w projekcie Corvus. Przeczytaj CLAUDE.md.

Zainicjuj projekt Corvus używając uv jako package managera.
Utwórz strukturę katalogów:
agent/src/{domain,application,infrastructure} i agent/tests/domain/.

Uruchom: uv python pin 3.12

Skonfiguruj pyproject.toml z:
- requires-python = ">=3.12,<3.14"
- [build-system] hatchling
- [tool.ruff] line-length=88, select=["E","F","I","N","UP","ANN","S","B"]
- [tool.pyright] pythonVersion="3.12", typeCheckingMode="strict"
- [tool.pytest.ini_options] asyncio_mode="auto"
- [tool.coverage.report] fail_under=80

Dodaj zależności przez uv add:
- prod: fastapi pydantic structlog langchain langgraph langchain-anthropic
- dev: pytest pytest-asyncio pytest-cov ruff pyright

Dodaj .env.example z: MODEL_BACKEND, ANTHROPIC_API_KEY,
LANGCHAIN_TRACING_V2, LANGCHAIN_API_KEY, REDIS_URL, DATABASE_URL,
FERNET_KEY, JWT_SECRET.

Dodaj .gitignore ignorujący: .env, __pycache__, .venv, .pyright,
.ruff_cache, dist/, .uv/, .claude/.

Weryfikacja: uv run ruff check . i uv run pyright muszą
przechodzić bez błędów.
```

---

### Sesja 1.2 — encje domenowe
```

Read CLAUDE.md. Create domain entities in agent/src/domain/.

metadata.py — Value Object:
  ThesisMetadata(frozen=True): author: str, title: str,
  year: int, field_of_study: str

analysis.py — Entities:
  FindingSeverity(Enum): CRITICAL, MAJOR, MINOR
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
  EvaluationStatus(Enum): UPLOADED, ANALYZING, ANALYZED,
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

### Sesja 1.3 — pierwszy węzeł LangGraph
```
Jesteśmy w projekcie Corvus. Przeczytaj CLAUDE.md.

Stan projektu: sesja 1.2 zakończona — encje domenowe
w agent/src/domain/ z testami przechodzącymi.

Utwórz TypedDict stanu grafu w agent/src/application/state.py:
- AnalysisState: thesis_id: str, text: str, guidelines: str,
  findings: list[Finding], scores: list[Score],
  review: Review | None, error: str | None

Zaimplementuj węzeł analyze_structure w
agent/src/application/nodes/structure.py:
- funkcja analyze_structure(state: AnalysisState) -> AnalysisState
- używa ChatAnthropic przez llm_factory (jeszcze nie istnieje —
  utwórz placeholder zwracający ChatAnthropic z env ANTHROPIC_API_KEY)
- prompt systemowy: analiza struktury rozdziałów pracy dyplomowej
- zwraca stan z uzupełnioną listą findings (tylko strukturalne)
- obsługuje wyjątek i zapisuje do state.error

Dodaj LANGCHAIN_TRACING_V2=true i LANGCHAIN_PROJECT=corvus
do .env.example.

Napisz test w agent/tests/application/test_structure_node.py
mockujący ChatAnthropic przez unittest.mock.patch.
Test weryfikuje że węzeł zwraca AnalysisState z niepustą
listą findings gdy mock zwraca poprawną odpowiedź,
oraz że error jest ustawiony gdy mock rzuca wyjątek.

Weryfikacja: uv run pytest agent/tests/ -v
i uv run ruff check . i uv run pyright bez błędów.
```

---

### Sesja 1.4 — graf LangGraph
```
Jesteśmy w projekcie Corvus. Przeczytaj CLAUDE.md.

Stan projektu: sesja 1.3 zakończona — węzeł analyze_structure
z testem, AnalysisState, placeholder llm_factory.

W agent/src/application/graph.py zbuduj graf LangGraph:
- StateGraph z AnalysisState
- węzły: analyze_structure (zaimplementowany),
  analyze_methodology (stub — zwraca state bez zmian),
  check_requirements (stub — zwraca state bez zmian),
  generate_review (stub — zwraca state bez zmian)
- przepływ: START → analyze_structure → analyze_methodology
  → check_requirements → generate_review → END
- funkcja build_analysis_graph() -> CompiledStateGraph

Napisz test w agent/tests/application/test_graph.py
mockujący wszystkie węzły. Test weryfikuje że:
1. graf przechodzi przez wszystkie węzły w kolejności
2. stan jest poprawnie przekazywany między węzłami
3. graph.invoke() zwraca AnalysisState

Weryfikacja: uv run pytest agent/tests/ -v --tb=short
i uv run ruff check . i uv run pyright bez błędów.
```

---

## Faza 2 — dokument i kolejkowanie (tydzień 3–4)

### Sesja 2.1 — serwis parser
```
Jesteśmy w projekcie Corvus. Przeczytaj CLAUDE.md.

Stan projektu: faza 1 zakończona — graf LangGraph z 4 węzłami
(1 zaimplementowany, 3 stuby), wszystkie testy przechodzą.

Utwórz mikroserwis parser/ z FastAPI:
- parser/src/domain/document.py: dataclass Document(text, pages, format)
- parser/src/application/extractor.py: funkcje extract_pdf(file: bytes)
  i extract_docx(file: bytes) zwracające Document
  PDF przez PyMuPDF (fitz), DOCX przez python-docx
- parser/src/infrastructure/router.py: FastAPI router,
  endpoint POST /extract przyjmujący UploadFile,
  zwracający {"text": str, "pages": int, "format": str}
  obsługa błędów: 422 dla nieobsługiwanego formatu,
  500 dla błędu ekstrakcji z logiem przez structlog
- parser/main.py: FastAPI app z routerem i /health endpointem
- parser/pyproject.toml: osobny projekt uv z Python 3.12,
  zależności: fastapi, uvicorn, pymupdf, python-docx, structlog

Utwórz parser/tests/fixtures/ z mini plikiem test.pdf
i test.docx (możesz użyć fpdf2 i python-docx do ich generowania
w conftest.py).

Napisz testy w parser/tests/test_extractor.py
i parser/tests/test_router.py z TestClient.

Weryfikacja: uv run pytest parser/tests/ -v
i uv run ruff check parser/ i uv run pyright parser/ bez błędów.
```

---

### Sesja 2.2 — Celery + Redis
```
Jesteśmy w projekcie Corvus. Przeczytaj CLAUDE.md.

Stan projektu: sesja 2.1 zakończona — mikroserwis parser
z testami przechodzącymi.

Dodaj do agent/ zależności: uv add celery redis

W agent/src/application/tasks.py utwórz zadanie Celery:
- funkcja analyze_thesis(thesis_id: str, text: str,
  guidelines: str) -> dict
- dekorator @shared_task(bind=True, max_retries=3,
  default_retry_delay=60)
- woła build_analysis_graph().invoke(state)
- w bloku except: raise self.retry(exc=exc)
- zwraca słownik z wynikiem analizy

W agent/src/infrastructure/celery_app.py:
- konfiguracja Celery z REDIS_URL z env przez pydantic-settings
- broker_url i result_backend na Redis
- task_serializer="json", accept_content=["json"]

Napisz test w agent/tests/application/test_tasks.py:
- mockuj build_analysis_graph i Redis
- weryfikuj że zadanie woła graf z poprawnymi argumentami
- weryfikuj że retry jest wywołany przy wyjątku

Weryfikacja: uv run pytest agent/tests/ -v
i uv run ruff check agent/ i uv run pyright agent/ bez błędów.
```

---

### Sesja 2.3 — model selector + pozostałe węzły
```
Jesteśmy w projekcie Corvus. Przeczytaj CLAUDE.md.

Stan projektu: sesja 2.2 zakończona — Celery z Redis,
zadanie analyze_thesis z retry.

W agent/src/infrastructure/llm_factory.py zastąp placeholder
pełną implementacją:
- funkcja get_llm() -> BaseChatModel
- match settings.model_backend:
    "claude"  → ChatAnthropic(model="claude-sonnet-4-20250514")
    "ollama"  → ChatOllama(model=settings.ollama_model,
                           base_url=settings.ollama_base_url)
    "openai"  → ChatOpenAI(model="gpt-4o")
    default   → ValueError z czytelnym komunikatem

Zaimplementuj pozostałe 3 węzły (zastąp stuby):
- analyze_methodology: sprawdza metodologię i źródła
- check_requirements: RAG — sprawdza zgodność z wytycznymi
  (na razie bez prawdziwego RAG — prompt z guidelines w state)
- generate_review: generuje Review z Score dla każdego kryterium

Napisz testy parametryzowane dla llm_factory:
@pytest.mark.parametrize("backend", ["claude", "ollama", "openai"])
mockujące każdy wariant.

Napisz testy dla każdego nowego węzła.

Weryfikacja: uv run pytest agent/tests/ -v --cov=agent/src
i uv run ruff check agent/ i uv run pyright agent/ bez błędów.
Pokrycie musi być >= 80%.
```

---

## Faza 3 — API i baza (tydzień 5–6)

### Sesja 3.1 — gateway + auth
```
Jesteśmy w projekcie Corvus. Przeczytaj CLAUDE.md.

Stan projektu: faza 2 zakończona — parser, Celery, model selector,
wszystkie 4 węzły LangGraph zaimplementowane.

Utwórz mikroserwis gateway/ z FastAPI:
- gateway/src/domain/user.py: dataclass User(id, email, role)
  Role(Enum): ADMIN, PROMOTOR
- gateway/src/application/auth.py: funkcje create_token(user) -> str,
  verify_token(token) -> User używające python-jose i JWT_SECRET z env
- gateway/src/infrastructure/router.py:
  POST /auth/login → {"access_token": str, "token_type": "bearer"}
  POST /analysis → {"task_id": str} (wymaga auth, wysyła do Celery)
  GET  /analysis/{task_id} → {"status": str, "result": dict | None}
  GET  /health → {"status": "ok"}
- Dependency Injection: get_current_user przez Bearer token
- gateway/pyproject.toml: fastapi, uvicorn, python-jose,
  celery, redis, pydantic-settings, structlog

Napisz testy z TestClient mockując Celery:
- test logowania z poprawnymi i błędnymi danymi
- test endpointów z tokenem i bez tokena
- test statusu zadania

Weryfikacja: uv run pytest gateway/tests/ -v
i uv run ruff check gateway/ i uv run pyright gateway/ bez błędów.
```

---

### Sesja 3.2 — Postgres + Alembic
```
Jesteśmy w projekcie Corvus. Przeczytaj CLAUDE.md.

Stan projektu: sesja 3.1 zakończona — gateway z JWT auth
i endpointami.

Dodaj do gateway/ i agent/: uv add sqlalchemy asyncpg alembic

W gateway/src/infrastructure/models.py utwórz modele SQLAlchemy 2.0:
- UserModel: id (UUID), email, role, hashed_password, created_at
- AnalysisModel: id (UUID), thesis_id, user_id (FK), status,
  result (JSON), created_at, updated_at

W gateway/src/infrastructure/repositories.py:
- AnalysisRepository: save(analysis) i find_by_id(id) jako async
- UserRepository: find_by_email(email) jako async

Zainicjuj Alembic: alembic init gateway/alembic
Utwórz pierwszą migrację: alembic revision --autogenerate
  -m "initial schema"

Napisz testy integracyjne z pytest-asyncio używające
SQLite w pamięci (sqlite+aiosqlite:///:memory:):
- test zapisu i odczytu Analysis
- test zapisu i odczytu User

Weryfikacja: uv run pytest gateway/tests/ -v
i uv run ruff check gateway/ i uv run pyright gateway/ bez błędów.
```

---

### Sesja 3.3 — secret vault
```
Jesteśmy w projekcie Corvus. Przeczytaj CLAUDE.md.

Stan projektu: sesja 3.2 zakończona — Postgres z Alembic,
repozytoria async.

W gateway/src/infrastructure/secrets.py:
- klasa SecretService z __init__(self, key: bytes)
- encrypt(plain: str) -> str używając cryptography.fernet.Fernet
- decrypt(token: str) -> str
- FERNET_KEY ładowany z env przez pydantic-settings

Dodaj do UserModel pole api_key_encrypted: str | None

W gateway/src/infrastructure/router.py dodaj:
- PATCH /settings/api-key (tylko rola ADMIN):
  przyjmuje {"api_key": str, "provider": str},
  szyfruje i zapisuje do DB
- GET /settings/api-key/status: zwraca {"configured": bool}
  bez odkrywania klucza

Napisz testy:
- test szyfrowania i deszyfrowania z fixture kluczem testowym
- test że endpoint nie zwraca plain text klucza nigdy
- test że ADMIN może ustawić klucz, PROMOTOR nie może

Weryfikacja: uv run pytest gateway/tests/ -v --cov=gateway/src
i uv run ruff check gateway/ i uv run pyright gateway/ bez błędów.
Pokrycie >= 80%.
```

---

## Faza 4 — frontend (tydzień 7–8)

### Sesja 4.1 — setup Next.js + upload
```
Jesteśmy w projekcie Corvus. Przeczytaj CLAUDE.md.

Stan projektu: faza 3 zakończona — gateway z auth, Postgres,
secret vault.

Utwórz frontend/ z Next.js App Router i TypeScript strict:
- npx create-next-app@latest frontend --typescript --app
  --tailwind --eslint --no-src-dir
- skonfiguruj tsconfig.json strict: true
- dodaj: npm install vitest @testing-library/react
  @testing-library/user-event react-dropzone swr zod
  react-hook-form

Wygeneruj typy API z OpenAPI schema gateway:
- npm install -D openapi-typescript
- dodaj skrypt: "gen-types": "openapi-typescript
  http://localhost:8000/openapi.json -o src/lib/api.types.ts"

Utwórz stronę /analysis:
- komponent FileUpload (react-dropzone): akceptuje PDF i DOCX,
  max 50MB, pokazuje nazwę i rozmiar pliku
- hook useAnalysis: POST /analysis → task_id,
  polling GET /analysis/{task_id} co 3s przez useSWR
  zatrzymuje polling gdy status === "done" lub "error"
- komponent AnalysisResult: wyświetla findings pogrupowane
  po severity, scores jako progress bary, summary i recommendation

Napisz testy Vitest + Testing Library:
- test FileUpload: akceptuje właściwe formaty, odrzuca inne
- test useAnalysis: polling zatrzymuje się przy "done"
- test AnalysisResult: renderuje findings i scores

Weryfikacja: npm run typecheck i npm test i npm run lint
bez błędów.
```

---

### Sesja 4.2 — panel admina + logowanie
```
Jesteśmy w projekcie Corvus. Przeczytaj CLAUDE.md.

Stan projektu: sesja 4.1 zakończona — strona /analysis
z uploadem, pollingiem i wyświetlaniem wyników.

Utwórz stronę /login:
- formularz (React Hook Form + Zod): email, password
- walidacja: email poprawny format, password min 8 znaków
- wywołuje POST /auth/login, zapisuje token w httpOnly cookie
  przez API route Next.js (nie localStorage)
- redirect do /analysis po sukcesie

Utwórz stronę /admin (chroniona — redirect do /login
jeśli brak tokena lub rola !== ADMIN):
- sekcja "Model AI": radio buttons LOCAL/CLOUD,
  pole na API key (type="password" z togglem widoczności),
  przycisk zapisz → PATCH /settings/api-key
- sekcja "Wytyczne": dropzone na PDF wytycznych uczelnianych,
  lista załadowanych plików z datą
- sekcja "Użytkownicy": tabela z listą promotorów

Middleware Next.js do ochrony /admin i /analysis
(sprawdza cookie z tokenem).

Napisz testy:
- test formularza logowania: walidacja, submit, redirect
- test /admin: redirect gdy brak tokena
- test sekcji API key: toggle widoczności, submit

Weryfikacja: npm run typecheck i npm test i npm run lint
bez błędów.
```

---

## Faza 5 — CI/CD i jakość (tydzień 9–10)

### Sesja 5.1 — docker-compose
```
Jesteśmy w projekcie Corvus. Przeczytaj CLAUDE.md.

Stan projektu: faza 4 zakończona — frontend z logowaniem,
uploadem i panelem admina.

Utwórz infra/docker-compose.yml ze wszystkimi serwisami:
- frontend: build ./frontend, port 3000, depends_on gateway
- gateway: build ./gateway, port 8000, env_file .env,
  depends_on postgres redis, healthcheck GET /health
- parser: build ./parser, port 8001, healthcheck GET /health
- agent: build ./agent, command: celery worker,
  env_file .env, depends_on redis postgres ollama
- flower: image mher/flower, port 5555, depends_on redis
- ollama: image ollama/ollama, port 11434, volumes ollama_data
- redis: image redis:7-alpine, port 6379,
  healthcheck redis-cli ping
- postgres: image postgres:16-alpine, port 5432,
  volumes postgres_data, healthcheck pg_isready
- jenkins: image jenkins/jenkins:lts, port 8080,
  volumes jenkins_data
- sonarqube: image sonarqube:community, port 9000,
  volumes sonarqube_data

Utwórz Dockerfile dla każdego serwisu Python:
- multi-stage build: builder (uv sync) + runtime (bez dev deps)
- non-root user
- healthcheck

Utwórz infra/docker-compose.override.yml dla lokalnego dev:
- mounted volumes dla hot-reload
- DEBUG=true

Weryfikacja: docker-compose config bez błędów,
docker-compose up --build uruchamia wszystkie serwisy.
```

---

### Sesja 5.2 — GitHub Actions + pre-commit
```
Jesteśmy w projekcie Corvus. Przeczytaj CLAUDE.md.

Stan projektu: sesja 5.1 zakończona — docker-compose
z wszystkimi serwisami.

Utwórz .github/workflows/ci.yml:
- trigger: push i pull_request na main i develop
- job test-gateway: uv run pytest gateway/tests/ --cov-report=xml
  + uv run ruff check gateway/ + uv run pyright gateway/
- job test-parser: analogicznie dla parser/
- job test-agent: analogicznie dla agent/
- job test-frontend: npm ci + npm run typecheck + npm test
- job sonarqube: SonarSource/sonarqube-scan-action@v2
  needs: [test-gateway, test-parser, test-agent, test-frontend]
  secrets: SONAR_TOKEN, SONAR_HOST_URL

Utwórz .github/workflows/cd.yml:
- trigger: push na main (po merge PR)
- build i push obrazów Docker na GHCR
- SSH na serwer i docker-compose pull + up -d

Utwórz .pre-commit-config.yaml:
- ruff check i ruff format dla Python
- prettier dla TypeScript/JSON
- pyright dla Python
- check-added-large-files (max 1MB)
- detect-private-key

Utwórz infra/sonarqube/sonar-project.properties.

Weryfikacja: pre-commit run --all-files bez błędów.
```

---

### Sesja 5.3 — Jenkinsfile
```
Jesteśmy w projekcie Corvus. Przeczytaj CLAUDE.md.

Stan projektu: sesja 5.2 zakończona — GitHub Actions CI/CD,
pre-commit hooks.

Utwórz infra/jenkins/Jenkinsfile:
stages:
1. Checkout: git checkout
2. Test Python: uv run pytest dla każdego serwisu równolegle
3. Test TypeScript: npm ci + npm test w frontend/
4. SonarQube: sonar-scanner z wynikami pokrycia
5. Build images: docker build dla każdego serwisu
6. Push to GHCR: docker push (tylko na main)
7. Deploy: SSH + docker-compose pull + up -d (tylko na main)
8. Healthcheck: curl wszystkich /health endpointów
9. Notify: email przy failure

Użyj Jenkins Credentials dla:
- GITHUB_TOKEN (GHCR push)
- SSH_KEY (deploy na serwer)
- SONAR_TOKEN

Utwórz README.md dla projektu:
- opis projektu Corvus
- wymagania (Docker, uv, Node 26)
- instrukcja uruchomienia lokalnie (5 kroków)
- architektura (krótki opis serwisów)
- zmienne środowiskowe (tabela)

Weryfikacja: Jenkinsfile ma poprawną składnię Groovy
(można sprawdzić przez Jenkins Pipeline Linter).
```

---

## Stan projektu

> Aktualizuj tę sekcję po każdej sesji.

| Sesja | Status | Data | Notatka |
|---|---|---|---|
| 1.1 setup | ✅ | — | struktura, pyproject.toml, uv, Python 3.12 |
| 1.2 encje | ✅ | 2026-05-24 | 4 pliki domain, 23 testy, pokrycie 100% |
| 1.3 węzeł | ⬜ | — | — |
| 1.4 graf | ⬜ | — | — |
| 2.1 parser | ⬜ | — | — |
| 2.2 Celery | ⬜ | — | — |
| 2.3 modele | ⬜ | — | — |
| 3.1 gateway | ⬜ | — | — |
| 3.2 Postgres | ⬜ | — | — |
| 3.3 secrets | ⬜ | — | — |
| 4.1 upload | ⬜ | — | — |
| 4.2 admin | ⬜ | — | — |
| 5.1 Docker | ⬜ | — | — |
| 5.2 CI/CD | ⬜ | — | — |
| 5.3 Jenkins | ⬜ | — | — |

---

## Checklist przed każdym commitem

- [ ] `uv run ruff check .` — bez błędów
- [ ] `uv run pyright` — bez błędów
- [ ] `uv run pytest --cov` — wszystkie testy przechodzą, pokrycie >= 80%
- [ ] brak `.env` w staged files (`git status`)
- [ ] commit message w formacie `feat:` / `fix:` / `test:` / `chore:`