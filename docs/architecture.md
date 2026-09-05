# Corvus — architektura systemu

> Dokument referencyjny dla Claude Code i developerów.
> Aktualizuj przy każdej znaczącej zmianie architektury.
>
> Ostatnia aktualizacja: 2026-09-05 — po ekstrakcji `identity` jako
> osobnego serwisu i przejściu `gateway` na czyste proxy.

---

## ⚠ Zaplanowany pivot — architektura docelowa jeszcze niezaimplementowana

Poniższy dokument opisuje **stan faktyczny** (4 serwisy Python: gateway/identity/parser/agent).
2026-09-05 podjęto decyzję o zmianie scope'u Corvusa (z analizy jednego dokumentu na
platformę mentoringową dla promotorów — studenci, notatki, cykl predefiniowanych akcji AI)
oraz o konsolidacji do **2 serwisów** (`app` + `agent`). Żadna z tych zmian nie jest jeszcze
wdrożona w kodzie — plan i uzasadnienie:

- [docs/adr/](adr/) — 5 ADR-ów: [0001](adr/0001-ai-first-mentoring-platform-pivot.md) (pivot scope'u),
  [0002](adr/0002-consolidate-services-into-app-and-agent.md) (konsolidacja serwisów),
  [0003](adr/0003-postgres-pgvector-for-persistence-and-rag.md) (Postgres/pgvector),
  [0004](adr/0004-self-hosted-default-model-with-byok.md) (model/BYOK),
  [0005](adr/0005-predefined-actions-not-open-chat.md) (predefiniowane akcje zamiast czatu)
- [docs/specs/mentoring-platform-implementation-plan.md](specs/mentoring-platform-implementation-plan.md) — plan fazowania (Faza 0–6) z listą plików do zmiany per faza

Nie edytuj sekcji poniżej pod kątem architektury docelowej, dopóki Faza 0 z planu
nie wyląduje — ten dokument ma opisywać to, co faktycznie działa, nie plany.
Po Fazie 0 (konsolidacja serwisów) ten plik zostanie przepisany pod nową architekturę
`app` + `agent`.

---

## Cel systemu

Corvus to lokalna aplikacja webowa wspomagająca promotorów
i recenzentów w analizie studenckich prac dyplomowych.
System analizuje przesłany dokument (PDF/DOCX) pod kątem
struktury, metodologii i zgodności z wymogami uczelnianymi,
a następnie generuje szkic recenzji.

Projekt służy jednocześnie jako platforma edukacyjna do nauki
nowoczesnego stacku Python + TypeScript w architekturze
microservices z DDD.

---

## Bounded Contexts (DDD)

Każdy mikroserwis odpowiada jednemu Bounded Context.
Komunikacja między kontekstami wyłącznie przez API — nigdy
przez wspólną bazę danych.

| Context | Serwis | Odpowiedzialność |
|---|---|---|
| document | parser | ekstrakcja tekstu z PDF i DOCX |
| analysis | agent | orkiestracja LangGraph, węzły analizy |
| review | agent | generowanie recenzji, ton, ocena punktowa |
| identity | identity | autentykacja, użytkownicy, role/permissions, klucze API |
| — | gateway | brak własnej domeny — czyste reverse proxy + JWT |

`identity` zostało wydzielone z gateway w trakcie implementacji
(patrz [Zmiany względem pierwotnego planu](sessions.md#zmiany-względem-pierwotnego-planu)
w `sessions.md`). Gateway nie ma już własnej bazy danych ani logiki
domenowej — weryfikuje JWT lokalnie (ten sam `JWT_SECRET`) i przekierowuje
żądania do `identity` lub `agent`.

---

## Serwisy (docker-compose)

| Serwis | Port | Stack | Opis |
|---|---|---|---|
| frontend | 3000 | Next.js, TypeScript | interfejs webowy |
| gateway | 8000 | FastAPI, Python | reverse proxy, weryfikacja JWT |
| identity | 8003 | FastAPI, Postgres | auth, użytkownicy, role, klucze API, audyt logowań |
| parser | 8001 | FastAPI, Python | ekstrakcja tekstu |
| agent | 8002 | FastAPI | HTTP API — przyjmowanie zadań analizy, status, historia |
| agent-worker | — | Celery | worker wykonujący graf LangGraph (ten sam obraz co `agent`) |
| ollama | 11434 | Ollama | lokalne modele LLM |
| redis | 6379 | Redis | broker Celery |
| postgres | 5432 | PostgreSQL 16 | dane identity + analiz |
| flower | 5555 | Celery Flower | monitoring kolejki |
| jenkins | 8080 | Jenkins LTS | CI/CD pipeline (jeszcze nieskonfigurowany — sesja 5.3) |
| sonarqube | 9000 | SonarQube CE | analiza jakości kodu (jeszcze nieskonfigurowany — sesja 5.2) |

`agent` i `agent-worker` współdzielą ten sam obraz Dockera —
`agent` uruchamia serwer FastAPI (przyjmuje żądania, zapisuje rekord
w Postgres, wrzuca zadanie do Celery), `agent-worker` uruchamia
`celery worker` i faktycznie wykonuje graf LangGraph.

---

## Przepływ danych

```
Użytkownik (przeglądarka)
  │
  ▼
frontend :3000  (Next.js route handlers jako proxy do gateway/parser)
  │  POST /api/analyze  (multipart: plik)
  ▼
parser :8001  → ekstrakcja tekstu (PyMuPDF / python-docx)
  │
  ▼
frontend  → POST /analysis (JWT w Authorization header)
  ▼
gateway :8000  (czyste proxy — weryfikuje JWT lokalnie, brak własnej domeny)
  │
  ├──► /auth/*, /users/*, /admin/*, /settings/*  →  identity :8003
  │      login, refresh (httpOnly cookie), rejestracja,
  │      role/permissions, audyt logowań, szyfrowanie kluczy API (Fernet)
  │
  └──► /analysis/*  →  agent :8002 (HTTP API)
         zapis rekordu AnalysisModel w Postgres
         Celery send_task(evaluation_id, text, metadata,
                           model, mode, review_tone, language)
         zwraca task_id natychmiast
         │
         ▼
       agent-worker (Celery worker)
         │
         ▼
       LangGraph StateGraph — zależny od `mode`:
         mode="full"         [struktura] → [metodologia] → [wymogi RAG] → [recenzja]
         mode="review_only"  → [recenzja] (bez węzłów pośrednich)
         │
         ▼
       model selector (agent/src/infrastructure/llm_factory.py)
         ├──► Ollama :11434   (model=qwen3:30b-a3b lub inny lokalny)
         └──► Claude API      (gdy model wskazuje na Claude)
         │
         ▼
       recenzja z tonem (ReviewTone: auto/enthusiastic/commendable/
       positive/diplomatic/reserved/negative) i językiem (pl/en)
         │
         ▼
       Postgres  (zapis AnalysisModel: status, result)
  ▼
frontend (polling GET /api/status/{taskId} co 3s)
  wyświetla wynik gdy status == "done"
```

---

## Struktura repozytorium

```
corvus/
│
├── frontend/                  # Next.js App Router, TypeScript
│   ├── app/
│   │   ├── page.tsx            # landing page
│   │   ├── login/               # logowanie
│   │   ├── analysis/            # upload + wynik + historia
│   │   │   └── history/
│   │   ├── admin/                # panel admina
│   │   │   ├── users/            # zarządzanie użytkownikami
│   │   │   └── login-events/     # audyt logowań
│   │   ├── profile/               # profil użytkownika, zmiana hasła
│   │   └── api/                    # route handlers — proxy do gateway/parser
│   │       ├── auth/{login,logout,refresh}/
│   │       ├── analyze/            # upload → parser
│   │       ├── analysis/           # → gateway → agent
│   │       ├── status/[taskId]/
│   │       ├── users/
│   │       └── admin/
│   ├── components/
│   ├── lib/
│   ├── hooks/
│   ├── middleware.ts            # ochrona /admin i /analysis (cookie JWT)
│   ├── vitest.config.ts
│   ├── eslint.config.mjs
│   └── tsconfig.json            # strict: true
│
├── gateway/                    # FastAPI — czyste reverse proxy, brak domeny/bazy
│   ├── src/
│   │   └── infrastructure/
│   │       ├── router.py        # proxy do identity i agent (httpx.AsyncClient)
│   │       └── settings.py      # IDENTITY_URL, AGENT_URL
│   ├── tests/
│   └── pyproject.toml
│
├── identity/                   # FastAPI, Postgres — auth i użytkownicy
│   ├── src/
│   │   ├── domain/
│   │   │   └── user.py          # Role, Permission, User, UserRegistration
│   │   │                          (email-validator, uprawnienia per-rola)
│   │   ├── application/
│   │   │   ├── auth.py          # create/verify access+refresh tokens (JWT)
│   │   │   └── user_service.py  # rejestracja, uwierzytelnianie, hashe (bcrypt)
│   │   └── infrastructure/
│   │       ├── router.py        # /auth/*, /users/*, /admin/*, /settings/*
│   │       ├── models.py        # SQLAlchemy — UserModel, LoginEventModel
│   │       ├── repositories.py
│   │       ├── secrets.py       # Fernet encryption kluczy API
│   │       ├── token_store.py   # RefreshTokenStore (Redis, revocation)
│   │       └── limiter.py       # rate limiting na /auth/login
│   ├── alembic/
│   ├── tests/
│   └── pyproject.toml
│
├── parser/                     # FastAPI, PyMuPDF, python-docx
│   ├── src/
│   │   ├── domain/
│   │   │   └── document.py      # Document dataclass
│   │   ├── application/
│   │   │   └── extractor.py     # extract_pdf, extract_docx
│   │   └── infrastructure/
│   │       └── router.py        # POST /extract
│   ├── tests/
│   │   └── fixtures/            # test.pdf, test.docx
│   └── pyproject.toml
│
├── agent/                      # FastAPI (HTTP API) + Celery + LangGraph
│   ├── src/
│   │   ├── domain/
│   │   │   ├── analysis.py      # ThesisAnalysis, Finding, FindingSeverity,
│   │   │   │                      ReviewTone, ThesisType
│   │   │   ├── evaluation.py    # ThesisEvaluation (Aggregate Root) — state machine
│   │   │   ├── metadata.py      # ThesisMetadata (Value Object)
│   │   │   └── review.py        # Review, Score
│   │   ├── application/
│   │   │   ├── state.py         # AnalysisState (TypedDict) — model/mode/tone/language
│   │   │   ├── graph.py         # build_analysis_graph(mode="full"|"review_only")
│   │   │   ├── guidelines.py    # loader wytycznych uczelnianych/promotora
│   │   │   ├── nodes/
│   │   │   │   ├── structure.py
│   │   │   │   ├── methodology.py
│   │   │   │   ├── requirements.py
│   │   │   │   └── review.py
│   │   │   ├── prompts/          # system prompty per węzeł + wytyczne
│   │   │   └── tasks.py          # Celery task analyze_thesis
│   │   └── infrastructure/
│   │       ├── api/
│   │       │   ├── router.py    # POST/GET /analysis, GET /analysis/{task_id}
│   │       │   └── auth.py      # lokalna weryfikacja JWT (bez wołania identity)
│   │       ├── celery_app.py
│   │       ├── llm_factory.py   # model selector
│   │       ├── models.py        # SQLAlchemy — AnalysisModel
│   │       └── repositories.py
│   ├── prompts/                  # pliki wytycznych (guidelines)
│   ├── tests/
│   └── pyproject.toml
│
├── infra/
│   ├── docker-compose.yml        # 12 serwisów: frontend, gateway, identity,
│   │                                parser, agent, agent-worker, flower, ollama,
│   │                                redis, postgres, jenkins, sonarqube
│   └── docker-compose.override.yml  # lokalne overrides (hot-reload, DEBUG)
│
├── docs/
│   ├── architecture.md          ← ten plik
│   ├── sessions.md               # plan sesji Claude Code + stan projektu
│   ├── technical-debt.md         # dług techniczny
│   └── specs/                    # specyfikacje pojedynczych funkcji
│
├── .github/workflows/            # jeszcze nieutworzone — sesja 5.2
├── .pre-commit-config.yaml       # jeszcze nieutworzony — sesja 5.2
├── .env.example
├── Makefile                      # skróty do docker-compose
├── CLAUDE.md
└── README.md
```

---

## Zasady DDD

### Reguła zależności (najważniejsza)

```
infrastructure → application → domain
                               ↑
                    zero importów z zewnątrz
```

Warstwa `domain/` nie importuje nic z FastAPI, LangChain,
SQLAlchemy ani żadnego frameworka. Zawiera wyłącznie
czystą logikę biznesową jako dataclasses i enums.

`gateway/` jest wyjątkiem świadomym: nie ma warstwy `domain/`
ani `application/`, ponieważ nie ma własnej logiki biznesowej —
to czysty adapter HTTP → HTTP.

### Przykład — warstwa domain (identity)

```python
# identity/src/domain/user.py
class Role(StrEnum):
    ADMIN = "admin"
    PROMOTOR = "promotor"

class Permission(StrEnum):
    MANAGE_USERS = "manage_users"
    VIEW_ALL_ANALYSES = "view_all_analyses"
    SUBMIT_ANALYSIS = "submit_analysis"

_ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.PROMOTOR: frozenset({Permission.SUBMIT_ANALYSIS}),
}

@dataclass(frozen=True)
class User:
    id: UUID
    email: str
    role: Role
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def can(self, permission: Permission) -> bool:
        return permission in _ROLE_PERMISSIONS.get(self.role, frozenset())
```

### Przykład — gateway jako czyste proxy

```python
# gateway/src/infrastructure/router.py
@router.api_route("/auth/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_identity_auth(path: str, request: Request) -> Response:
    return await _proxy(request, settings.identity_url, f"/auth/{path}")
```

`_proxy()` przekazuje body, headers (w tym `Authorization` i `Cookie`)
i query params, obsługuje `httpx.ConnectError` (503) i timeout (504),
i loguje każde przekierowanie przez `structlog` z `request_id`.

### Przykład — model selector

```python
# agent/src/infrastructure/llm_factory.py
def get_llm(model: str) -> BaseChatModel:
    match settings.model_backend:
        case "claude":
            return ChatAnthropic(model="claude-sonnet-4-20250514")
        case "ollama":
            return ChatOllama(model=model, base_url=settings.ollama_base_url)
        case "openai":
            return ChatOpenAI(model="gpt-4o")
        case _:
            raise ValueError(f"Nieznany MODEL_BACKEND: {settings.model_backend}")
```

---

## Tooling

### Python (każdy serwis)

| Narzędzie | Rola |
|---|---|
| `uv` | package manager, środowisko wirtualne |
| `ruff` | linter + formatter |
| `pyright` | static type checker (strict mode) |
| `pytest` + `pytest-asyncio` + `pytest-cov` | testy (min 80% coverage) |
| `structlog` | logowanie w formacie JSON |
| `pydantic-settings` | konfiguracja z env |
| `alembic` | migracje bazy danych (identity, agent) |
| `email-validator` | walidacja adresów e-mail (identity) |
| `fastapi-limiter` | rate limiting (identity — `/auth/login`) |

### TypeScript (frontend)

| Narzędzie | Rola |
|---|---|
| `vitest` + `@testing-library/react` | testy |
| `eslint` + `@typescript-eslint` | linter |
| `prettier` | formatter |
| `zod` + `react-hook-form` | walidacja i formularze |
| `swr` | data fetching i polling |

---

## Zmienne środowiskowe

Pełna referencja: [.env.example](../.env.example).

| Zmienna | Serwis | Opis |
|---|---|---|
| `MODEL_BACKEND` | agent | `ollama` \| `claude` \| `openai` |
| `OLLAMA_MODEL` | agent | domyślny model, np. `qwen3:30b-a3b` |
| `OLLAMA_BASE_URL` | agent | `http://host.docker.internal:11434` lokalnie |
| `ANTHROPIC_API_KEY` | agent | klucz Claude API |
| `LANGCHAIN_TRACING_V2` / `LANGCHAIN_API_KEY` / `LANGCHAIN_PROJECT` | agent | LangSmith tracing (opcjonalne) |
| `DATABASE_URL` | identity, agent | PostgreSQL connection string |
| `REDIS_URL` | agent, identity | broker Celery + refresh token store |
| `JWT_SECRET` / `JWT_ALGORITHM` | identity, gateway, agent | wspólny sekret — każdy serwis weryfikuje JWT lokalnie |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | identity | TTL tokenów |
| `FERNET_KEY` | identity | szyfrowanie kluczy API użytkowników |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | identity | seed pierwszego konta admina (wymagane, min. 12 znaków hasła) |
| `IDENTITY_URL` | gateway | adres serwisu identity (`http://identity:8003`) |
| `AGENT_URL` | gateway | adres serwisu agent (`http://agent:8002`) |
| `SONAR_TOKEN` / `SONAR_HOST_URL` | CI/CD | jeszcze nieużywane — sesja 5.2 |

Generowanie kluczy:
```bash
# FERNET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# JWT_SECRET
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## CI/CD pipeline

> Status: **nieukończone** — sesje 5.2 (GitHub Actions + pre-commit)
> i 5.3 (Jenkinsfile + README) z `sessions.md` jeszcze nie zrealizowane.
> Poniżej docelowy kształt z pierwotnego planu.

```
git push
  │
  ▼
GitHub Actions (ci.yml) — przy każdym PR
  ├── test-identity  (pytest + ruff + pyright)
  ├── test-gateway   (pytest + ruff + pyright)
  ├── test-parser    (pytest + ruff + pyright)
  ├── test-agent     (pytest + ruff + pyright)
  ├── test-frontend  (vitest + tsc + eslint)
  └── sonarqube      (skan po przejściu testów)
  │
  ▼ (merge do main)
  │
Jenkins (Jenkinsfile)
  ├── Pull images z GHCR
  ├── docker-compose up -d
  └── Healthcheck wszystkich serwisów
```

---

## Bezpieczeństwo

- `.env` zawsze w `.gitignore` — nigdy w repo
- JWT_SECRET współdzielony przez identity/gateway/agent — każdy serwis
  weryfikuje token lokalnie, bez wywołania sieciowego do identity
  (endpoint `/internal/token/introspect` istnieje dla przyszłych serwisów
  bez dostępu do sekretu, ale obecnie nieużywany)
- access token (15 min) + refresh token (30 dni) w httpOnly cookie,
  `secure`, `samesite=strict`, ograniczony do path `/auth/refresh`
- refresh tokeny odwoływalne przez `RefreshTokenStore` (Redis, JTI blacklist)
  — **ale bez rewokacji access tokenów** (patrz `technical-debt.md`)
- klucze API użytkowników szyfrowane Fernetem w Postgres (identity)
- każdy serwis ma non-root user w Dockerze
- audyt logowań (`LoginEventModel`) — IP, user-agent, sukces/porażka
- rate limiting na `/auth/login` (fastapi-limiter)
- Dependabot / Renovate Bot — **jeszcze nieskonfigurowane**
