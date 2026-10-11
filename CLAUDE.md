# Corvus — project kickoff

> Punkt wyjścia dla Claude Code i implementacji.  
> Wersja: 1.0 · Maj 2026

---

## 1. Cel projektu

Lokalna aplikacja webowa wspomagająca promotorów i recenzentów w analizie studenckich prac dyplomowych. System analizuje przesłany dokument (PDF/DOCX) pod kątem struktury, metodologii, zgodności z wymogami uczelnianymi i generuje szkic recenzji. Projekt służy jednocześnie jako platforma edukacyjna do nauki nowoczesnego stacku Python + TypeScript w architekturze microservices.

---

## 2. Wymagania funkcjonalne

- Upload dokumentu PDF lub DOCX przez interfejs webowy
- Ładowanie wytycznych uczelnianych i promotora (jednorazowo, jako kontekst stały)
- Analiza pracy w czterech wymiarach:
  - struktura i spójność rozdziałów
  - metodologia i źródła bibliograficzne
  - zgodność z wymogami uczelnianymi (RAG)
  - generowanie szkicu recenzji z oceną punktową
- Wybór modelu AI: lokalny (Ollama) lub komercyjny (Claude API / OpenAI)
- Historia analiz i raportów per użytkownik
- Panel administracyjny do zarządzania wytycznymi i kluczami API
- Monitoring kolejki zadań (Flower UI)

## Dokumentacja
- docs/sessions.md — plan sesji i prompty
- docs/architecture.md — architektura systemu

---

## 3. Architektura systemu

> ⚠ **Projekt jest w trakcie pivotu.** Scope zmienił się z analizy jednego
> dokumentu na platformę mentoringową (studenci, notatki, predefiniowane akcje AI).
> **Wszystkie sześć faz pivotu jest zrobionych**: konsolidacja serwisów, domena
> mentoringowa, sześć akcji AI, frontend oparty o studentów, BYOK, RAG nad
> wytycznymi (pgvector) i CI/CD. Decyzje: [docs/adr/](docs/adr/) · plan i status faz:
> [docs/specs/mentoring-platform-implementation-plan.md](docs/specs/mentoring-platform-implementation-plan.md).
> Sekcja 9 poniżej (kolejność implementacji) jest **nieaktualna** — zastąpiona tym planem.

### 3.1 Bounded Contexts (DDD)

Konteksty rozdzielone na poziomie pakietów i schematów Postgresa, nie sieci.

```
app/src/identity/    — autentykacja, użytkownicy, role/permissions, audyt, klucze API
app/src/document/    — ekstrakcja tekstu z PDF/DOCX (bezstanowa)
app/src/mentoring/   — studenci, notatki ze spotkań, wersje pracy (pliki, retencja), akcje AI
app/src/guidelines/  — katalog wytycznych uczelni: zestawy, wersje, rubryki, progi
agent/src/           — analysis + review: graf LangGraph, węzły, recenzja
```

### 3.2 Microservices (docker-compose)

| Serwis | Port | Stack | Bounded Context |
|---|---|---|---|
| frontend | 3000 | Next.js, TypeScript | — |
| app | 8000 | FastAPI, Postgres | identity + document + mentoring + guidelines |
| agent | 8002 | FastAPI, LangGraph | analysis + review |
| agent-worker | — | Celery | wykonuje graf (ten sam obraz co agent) |
| ollama | 11434 | Ollama | — |
| redis | 6379 | Redis | — |
| postgres | 5432 | PostgreSQL 16 + pgvector + Alembic | — |
| flower | 5555 | Celery Flower | — |
| jenkins | 8080 | Jenkins | — |
| sonarqube | 9000 | SonarQube CE | — |

Jedyny podział sieciowy: szybkie synchroniczne CRUD (`app`) vs wolne
asynchroniczne wywołania LLM (`agent`) — patrz ADR 0002.

### 3.3 Przepływ danych

```
Użytkownik
  → frontend (upload PDF/DOCX)
  → app :8000
      ├─ /auth/*, /users/*, /admin/*, /settings/*  — obsługiwane in-process
      ├─ /students/*   — roster + notatki ze spotkań, in-process
      ├─ /students/{id}/actions — akcje AI: kontekst składany w `app`,
      │                  wysyłka do agent POST /actions, polling, akceptacja;
      │                  rubryka wybranego zestawu wytycznych jedzie w kontekście
      ├─ /students/{id}/drafts — upload wersji pracy (plik + tekst), pobranie,
      │                  akceptacja wersji finalnej, retencja (ADR 0006)
      └─ /guidelines/* — katalog wytycznych; zapis pod /guidelines/admin
  → agent :8002 (POST /actions, GET /actions/{task_id})
  → Celery task (broker: Redis) → agent-worker
      status zapisywany do Postgresa: running → completed | failed
  → LangGraph — graf zależny od typu akcji
      → generate_review:      [Struktura ∥ Metodologia ∥ Wymogi ∥ Rozdział×N → Spójność]
                              → [Weryfikacja]
                              → [Wybór promotora]* → [Recenzja]
        (Rozdział×N: `Send` per rozdział z mapy dokumentu — streszczenie z cytatami;
         Spójność: czy wnioski wynikają z wyników, czy hipotezy rozstrzygnięte)
        (*tylko gdy promotor zaznaczył „Pokaż mi uwagi…”: `interrupt`, status
         `awaiting_input`, wznowienie POST …/actions/{id}/resume z indeksami uwag)
      → propose_topic:        [Propozycja tematu]
      → defence_questions:    [Pytania na obronę]
      → check_progress:       [Porównanie dwóch wersji]
      → evaluate_methodology: [Metodologia] → [Weryfikacja]
        (Weryfikacja: bez modelu — cytat każdej uwagi musi być w tekście,
         duplikaty z różnych analiz scalane; `agent/src/application/grounding.py`)
      → draft_meeting_note:   [Szkic notatki]
      → verify_bibliography:  [Lista pozycji] → [Crossref, potem katalogi bibliotek
                              (Biblioteka Narodowa, Open Library), bez modelu]
                              → [Agent ⇄ narzędzia tych źródeł]* → [Werdykty]
        (*tylko dla pozycji, których dopasowanie nie rozstrzygnęło; na zewnątrz
         idą wyłącznie opisy bibliograficzne, nigdy tekst pracy)
  → model selector
      → promotor wybiera przy akcji: własny klucz (BYOK) do Claude albo
        OpenAI — po jednym na dostawcę — albo Ollama (lokalny, domyślny);
        zapisany klucz nie jest używany, dopóki akcja o niego nie poprosi
        klucz jedzie osobnym argumentem taska, zaszyfrowany na czas kolejki
        (ADR 0012), i żyje w ContextVar tylko na czas przebiegu grafu — nigdy
        w stanie, który trafia do bazy
  → Postgres (zapis raportu)
  → frontend (polling → wyświetlenie raportu)
```

### 3.4 Model selector

Przełączanie modelu przez zmienną środowiskową lub klucz API w UI:

```python
# agent/infrastructure/llm_factory.py
match settings.model_backend:
    case "ollama":   return ChatOllama(model=settings.ollama_model)
    case "claude":   return ChatAnthropic(model="claude-sonnet-5-5")
    case "openai":   return ChatOpenAI(model="gpt-6.1-sol")
```

---

## 4. Struktura repozytorium

```
corvus/
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js App Router
│   │   ├── components/
│   │   ├── lib/              # API client, typy
│   │   └── hooks/
│   ├── vitest.config.ts
│   ├── eslint.config.mjs
│   ├── prettier.config.mjs
│   └── tsconfig.json
│
├── app/                      # identity + document + mentoring
│   ├── main.py               # montuje routery: identity, mentoring, health
│   ├── alembic_identity/     # lineage migracji schematu `identity`
│   ├── alembic_mentoring/    # lineage migracji schematu `mentoring`
│   ├── alembic_guidelines/   # lineage migracji schematu `guidelines`
│   ├── scripts/              # seed_admin, seed_guidelines, seed_demo, purge_drafts,
│   │                           build_thesis_docx (fikstury prac na demo)
│   ├── src/
│   │   ├── identity/
│   │   │   ├── domain/       # Role, Permission, User, UserRegistration
│   │   │   ├── application/  # auth.py (JWT), user_service.py (bcrypt)
│   │   │   └── infrastructure/  # dependencies, schemas, {auth,users,settings,
│   │   │                          admin}_router, router (agreguje), models,
│   │   │                          repositories, secrets, token_store, limiter
│   │   ├── mentoring/
│   │   │   ├── domain/       # student.py, draft.py, action.py, retention.py
│   │   │   ├── application/  # student_service (Caller, reguła własności),
│   │   │   │                   draft_service, retention_service, context,
│   │   │   │                   guidelines_port, agent_client,
│   │   │   │                   action_service, exceptions
│   │   │   └── infrastructure/  # dependencies, schemas, errors,
│   │   │                          {students,actions,drafts}_router,
│   │   │                          router (agreguje), orm/, repositories,
│   │   │                          retention (pętla sweepu), guidelines_adapter
│   │   ├── guidelines/       # domain/catalog.py, application/{catalog,
│   │   │                       admin_service}, infrastructure/ (router, orm…)
│   │   ├── document/         # document.py, extractor.py, outline.py
│   │   │                       (mapa dokumentu bez modelu, wołane in-process)
│   │   └── shared/           # settings, database, health, logging, middleware,
│   │                           files (port FileStore), sql_file_store, downloads
│   ├── tests/{test_identity,test_mentoring,test_guidelines,test_document,test_shared}/
│   ├── pyproject.toml
│   └── Dockerfile
│
├── agent/
│   ├── src/
│   │   ├── domain/
│   │   │   ├── analysis.py   # encje: ThesisAnalysis, Finding
│   │   │   └── review.py     # encje: Review, Score
│   │   ├── application/
│   │   │   ├── graph.py      # build_action_graph — graf per typ akcji
│   │   │   ├── excerpt.py    # fragment + mapa całości + reguły dla węzłów
│   │   │   │                   czytających tekst pracy (patrz `document/outline.py`)
│   │   │   ├── nodes/        # structure, methodology, requirements, review,
│   │   │   │                   propose_topic, defence_questions,
│   │   │   │                   check_progress, draft_meeting_note
│   │   │   └── tasks.py      # Celery: run_action
│   │   └── infrastructure/
│   │       ├── llm_factory.py   # BYOK (ContextVar) → Claude/OpenAI, inaczej Ollama
│   │       ├── embeddings.py    # model embeddingów (lokalny, zawsze)
│   │       ├── guideline_store.py  # wyszukiwanie chunków (pgvector)
│   │       ├── logging.py       # configure_logging — wołane z main.py i celery_app.py
│   │       ├── task_status.py
│   │       └── repositories.py
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
│
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.override.yml   # lokalne overrides
│   ├── jenkins/
│   │   └── Jenkinsfile
│   ├── sonarqube/
│   │   └── sonar-project.properties
│   └── postgres/
│       └── init.sql
│
├── .github/
│   └── workflows/
│       ├── ci.yml            # testy + SonarQube przy PR
│       └── cd.yml            # build + deploy przy merge do main
│
├── .pre-commit-config.yaml
├── .env.example
└── README.md
```

---

## 5. Tooling i jakość kodu

### 5.1 Python (każdy serwis)

```toml
# pyproject.toml
[tool.ruff]
line-length = 88
select = ["E", "F", "I", "N", "UP", "ANN", "S", "B"]

[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "strict"

[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "--cov=src --cov-report=xml"

[tool.coverage.report]
fail_under = 80
```

Zależności developerskie per serwis:
- `pytest`, `pytest-asyncio`, `pytest-cov`
- `ruff` (linter + formatter)
- `pyright` (static type checker)
- `pre-commit`
- `structlog` (JSON logging)
- `alembic` (migracje DB — `app` i `agent`, osobne lineage per schemat)

### 5.2 TypeScript (frontend)

```json
// package.json scripts
{
  "test":     "vitest run",
  "test:ui":  "vitest --ui",
  "lint":     "eslint src --max-warnings 0",
  "format":   "prettier --write src",
  "typecheck":"tsc --noEmit"
}
```

Zależności developerskie:
- `vitest` + `@testing-library/react`
- `eslint` + `@typescript-eslint/eslint-plugin`
- `prettier`
- `typescript` (strict mode)

### 5.3 Pre-commit hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-prettier
    hooks:
      - id: prettier
        types_or: [typescript, tsx, json]
  - repo: local
    hooks:
      - id: pyright
        name: pyright
        entry: pyright
        language: system
        types: [python]
      - id: pytest
        name: pytest (fast)
        entry: pytest -x -q --ignore=tests/integration
        language: system
        types: [python]
```

---

## 6. CI/CD pipeline

Pliki są w repo — poniżej tylko co gdzie leży i dlaczego tak:

| Plik | Co robi |
|---|---|
| [.github/workflows/ci.yml](.github/workflows/ci.yml) | PR i push na `main`: `app`, `agent`, `frontend`, `migrations`, `sonarqube` |
| [.pre-commit-config.yaml](.pre-commit-config.yaml) | `ruff --fix`, eslint, higiena plików, `detect-private-key` |
| [.github/workflows/cd.yml](.github/workflows/cd.yml) | po zielonym CI na `main`: obrazy → GHCR → ssh → `infra/deploy/deploy.sh` |
| [infra/deploy/](infra/deploy/) | produkcja: compose bez portów poza Caddy, backup, setup serwera — [docs/deploy.md](docs/deploy.md) |
| [infra/jenkins/Jenkinsfile](infra/jenkins/Jenkinsfile) | build → migracje → `compose up -d` → healthcheck (lokalnie; produkcja idzie przez `cd.yml`) |
| [infra/sonarqube/sonar-project.properties](infra/sonarqube/sonar-project.properties) | trzy pakiety, jeden projekt |

Zasady, które warto znać przed zmianą któregokolwiek z nich:

- **`pyright` w CI sprawdza `src`, nie `tests`.** Kod produkcyjny obu serwisów jest
  czysty w trybie strict i CI tego pilnuje; w testach zostaje ok. 250 błędów
  `reportUnknownMemberType` na `TestClient`/`httpx` — [dług](docs/technical-debt.md),
  nie wyciszona bramka.
- **Job `migrations` stawia schemat od zera** na obrazie `pgvector/pgvector:pg16`.
  Zwykły `postgres` przeszedłby CI i wywrócił się przy deployu na
  `CREATE EXTENSION vector`.
- **Produkcja (`corvus.saek.dev`) wdraża się z `cd.yml`, nie z Jenkinsa.**
  `.env` mieszka tylko na serwerze; `deploy.sh` czeka na healthchecki i sam
  wraca do poprzedniego obrazu, gdy nowy nie wstanie. Bez lokalnych modeli
  czatu (`LOCAL_MODELS_ENABLED=false`, ADR 0013), backup bazy codziennie.
- **Sonar jest pomijany, gdy nie ma `SONAR_TOKEN`** — czerwony krzyżyk na każdym
  buildzie forka uczy ludzi ignorować czerwone krzyżyki.
- **Hooki nie odpalają `pytest` ani `pyright`** — 55 s na commit to hook wyłączany
  przez `--no-verify`. Od tego jest CI.

Instalacja hooków: `uvx pre-commit install`.

---

## 7. Zasady DDD w projekcie

### Warstwa domain (czysta, zero frameworków)

```python
# agent/src/domain/analysis.py
from dataclasses import dataclass
from enum import Enum

class FindingSeverity(Enum):
    CRITICAL = "critical"
    MAJOR    = "major"
    MINOR    = "minor"

@dataclass(frozen=True)
class Finding:
    section:     str
    description: str
    severity:    FindingSeverity
    suggestion:  str

@dataclass
class ThesisAnalysis:
    thesis_id:    str
    findings:     list[Finding]
    requirements: list[str]

    def critical_count(self) -> int:
        return sum(1 for f in self.findings
                   if f.severity == FindingSeverity.CRITICAL)

    def is_ready_for_review(self) -> bool:
        return self.critical_count() == 0
```

### Warstwa application (use cases, Celery)

```python
# agent/src/application/tasks.py
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_action(self, action_id, action_type, student_id, context,
               model="qwen3:30b-a3b", language="pl") -> dict[str, Any]:
    task_id = self.request.id
    try:
        return _run_graph(task_id, _initial_state(
            action_id, action_type, student_id,
            _with_guidelines(action_type, context), model, language,
        ))
    except Exception as exc:
        _record_final_failure(self, task_id, exc)
        raise self.retry(exc=exc)
```

`_run_graph` zapisuje status do Postgresa przed i po wywołaniu grafu — wynik
akcji nie może zależeć od TTL backendu Celery w Redisie.

### Reguła: zależności idą tylko do wewnątrz

```
infrastructure → application → domain
                               ↑ zero importów z zewnątrz
```

---

## 8. Bezpieczeństwo kluczy API

```python
# app/src/identity/infrastructure/secrets.py
from cryptography.fernet import Fernet

class SecretService:
    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    def encrypt(self, plain: str) -> str:
        return self._fernet.encrypt(plain.encode()).decode()

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode()).decode()
```

Zasady:
- `.env` zawsze w `.gitignore`
- Klucze produkcyjne wyłącznie w GitHub Secrets i Jenkins Credentials
- Klucze API użytkowników w Postgres jako zaszyfrowany `text`, nigdy plain text
- Klucz usera (BYOK) odszyfrowywany wyłącznie w żądaniu, które go zaraz użyje,
  i tylko ten jeden, którego dostawcę wybrano dla akcji;
  do agenta jedzie osobnym argumentem taska, nigdy w kontekście ani w stanie grafu;
  w Redis leży zaszyfrowany (HKDF z `JWT_SECRET`), otwiera go dopiero worker
- `FERNET_KEY` generowany raz: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

---

## 9. Kolejność implementacji

> ⚠ **Pierwotny plan (Fazy 1–5) został zrealizowany i jest zamknięty** — historia
> w [docs/sessions.md](docs/sessions.md). Od 2026-09-05 obowiązuje nowy plan pivotu.

Aktualny plan i status faz:
**[docs/specs/mentoring-platform-implementation-plan.md](docs/specs/mentoring-platform-implementation-plan.md)**

| Faza | Zakres | Status |
|---|---|---|
| 0 | konsolidacja serwisów (gateway+identity+parser → app) | ✅ 2026-09-05 |
| 1 | model danych mentoringu: Student, MeetingNote, ThesisDraft, AgentAction | ✅ 2026-09-05 |
| 2 | pierwsza akcja AI end-to-end (`propose_topic`) + naprawa trwałości statusu | ✅ 2026-09-05 |
| 3 | pozostałe akcje (w tym `defence_questions`), upload wersji pracy, frontend mentoringowy; usunięcie przejściowych endpointów | ✅ 2026-09-06 |
| 4 | BYOK — klucz usera zamiast globalnego | ✅ 2026-09-06 |
| 5 | pgvector: RAG nad wytycznymi | ✅ 2026-09-06 |
| 6 | deploy + CI/CD (GitHub Actions, Jenkins, pre-commit) | ✅ 2026-09-06 |

Po pivocie: katalog wytycznych uczelni i pliki prac z retencją — ✅ 2026-09-23,
[ADR 0006](docs/adr/0006-guideline-catalog-and-thesis-file-retention.md) ·
[plan](docs/specs/guidelines-and-thesis-files-plan.md).

Modele lokalne udostępnia admin (`/admin/models`), promotor wybiera tylko z tej
listy, a `app` pilnuje tego przy każdej akcji —
[ADR 0007](docs/adr/0007-admin-managed-local-model-allowlist.md).
Admin i promotor to rozłączne role: admin nie widzi studentów ani prac —
[ADR 0008](docs/adr/0008-admin-and-promoter-are-separate-roles.md).
Twarde usuwanie studenta (z plikami i wynikami AI po stronie agenta) i pojedynczej
akcji — wszystko albo nic, bez agenta 503 —
[ADR 0009](docs/adr/0009-hard-delete-of-students-and-actions.md).
Każdy przebieg grafu ma checkpointy w Postgresie (wątek = id taska), taski są
potwierdzane po zakończeniu — padnięty worker wznawia recenzję od ostatniego
kroku, a checkpointy znikają, gdy przebieg ma wynik —
[ADR 0010](docs/adr/0010-graph-checkpoints-and-late-acks.md).
Promotor trzyma po jednym kluczu na dostawcę (`identity.user_api_keys`) i przy
każdej akcji wybiera, na czym ona pójdzie; brak wyboru to model lokalny, a
dostawca bez klucza to 409, nie cichy fallback —
[ADR 0011](docs/adr/0011-a-key-per-provider-chosen-per-action.md).
Klucz w kolejce Celery jest zaszyfrowany — przy late acks wiadomość leży w Redis
przez cały przebieg i widać ją we Flower —
[ADR 0012](docs/adr/0012-seal-the-provider-key-for-the-task-queue.md).
Na produkcji nie ma lokalnych modeli czatu: `LOCAL_MODELS_ENABLED=false`, akcja
bez dostawcy to 409, embeddingi zostają na lokalnej Ollamie —
[ADR 0013](docs/adr/0013-a-server-without-local-models.md).

---

## 10. Zmienne środowiskowe (.env.example)

```bash
# Model
MODEL_BACKEND=ollama                     # ollama | claude | openai
OLLAMA_MODEL=qwen3:30b-a3b
OLLAMA_BASE_URL=http://ollama:11434

# Claude API
ANTHROPIC_API_KEY=                       # uzupełnij lokalnie

# LangSmith
LANGCHAIN_TRACING_V2=false              # set to true + add key to enable LangSmith
LANGCHAIN_API_KEY=                       # uzupełnij lokalnie
LANGCHAIN_PROJECT=thesis-reviewer

# Baza danych
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/thesis_reviewer

# Redis
REDIS_URL=redis://redis:6379/0

# Bezpieczeństwo
FERNET_KEY=                              # wygeneruj: patrz sekcja 8
JWT_SECRET=                              # losowy string min 32 znaki
JWT_ALGORITHM=HS256

# Pliki prac (ADR 0006)
MAX_UPLOAD_BYTES=26214400                # 25 MB
RETENTION_SWEEP_INTERVAL_HOURS=24        # 0 = sweep tylko z `make purge-drafts`

# SonarQube
SONAR_TOKEN=                             # z panelu SonarQube
SONAR_HOST_URL=http://sonarqube:9000
```

---

## 11. Zasoby do nauki

| Temat | Zasób |
|---|---|
| LangGraph | [docs.langchain.com/langgraph](https://langchain-ai.github.io/langgraph/) |
| LangSmith | [docs.smith.langchain.com](https://docs.smith.langchain.com) |
| Celery | [docs.celeryq.dev](https://docs.celeryq.dev) |
| Redis Streams | [redis.io/docs/data-types/streams](https://redis.io/docs/data-types/streams/) |
| FastAPI | [fastapi.tiangolo.com](https://fastapi.tiangolo.com) |
| Ruff | [docs.astral.sh/ruff](https://docs.astral.sh/ruff) |
| Pyright | [github.com/microsoft/pyright](https://github.com/microsoft/pyright) |
| DDD (Evans) | _Domain-Driven Design_ — Eric Evans |
| SonarQube | [docs.sonarsource.com](https://docs.sonarsource.com) |
| Claude Code | [docs.claude.ai/claude-code](https://docs.anthropic.com/claude-code) |
