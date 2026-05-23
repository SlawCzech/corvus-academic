# Corvus — architektura systemu

> Dokument referencyjny dla Claude Code i developerów.
> Aktualizuj przy każdej znaczącej zmianie architektury.

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
| review | agent | generowanie recenzji i oceny |
| identity | gateway | autentykacja, użytkownicy, klucze API |

---

## Serwisy (docker-compose)

| Serwis | Port | Stack | Opis |
|---|---|---|---|
| frontend | 3000 | Next.js, TypeScript | interfejs webowy |
| gateway | 8000 | FastAPI, Python | API gateway, JWT auth |
| parser | 8001 | FastAPI, Python | ekstrakcja tekstu |
| agent | 8002 | Celery, LangGraph | analiza i recenzja |
| ollama | 11434 | Ollama | lokalne modele LLM |
| redis | 6379 | Redis Streams | broker Celery, cache |
| postgres | 5432 | PostgreSQL 16 | historia, wytyczne, raporty |
| flower | 5555 | Celery Flower | monitoring kolejki |
| jenkins | 8080 | Jenkins LTS | CI/CD pipeline |
| sonarqube | 9000 | SonarQube CE | analiza jakości kodu |

---

## Przepływ danych

```
Użytkownik (przeglądarka)
  │
  ▼
frontend :3000
  │  POST /analysis (multipart: plik + parametry)
  ▼
gateway :8000 (JWT auth → weryfikacja tokena)
  │
  ├──► parser :8001
  │      PyMuPDF / python-docx → czysty tekst
  │      zwraca: {text, pages, format}
  │
  ▼
  Celery task (analyze_thesis)
  │  zadanie wrzucone do Redis Streams
  │  gateway zwraca task_id natychmiast
  │
  ▼
agent :8002 (Celery worker)
  │
  ▼
LangGraph StateGraph
  │
  ├──► [węzeł 1] analyze_structure
  ├──► [węzeł 2] analyze_methodology
  ├──► [węzeł 3] check_requirements  ◄── wytyczne (RAG)
  └──► [węzeł 4] generate_review
  │
  ▼
model selector
  ├──► Ollama :11434  (MODEL_BACKEND=ollama)
  │      Qwen3.6-14B / 27B — lokalnie
  └──► Claude API    (MODEL_BACKEND=claude)
         claude-sonnet-4-20250514 — cloud
  │
  ▼
Postgres :5432
  (zapis raportu)
  │
  ▼
frontend (polling GET /analysis/{task_id} co 3s)
  wyświetla wynik gdy status == "done"
```

---

## Struktura repozytorium

```
corvus/
│
├── frontend/                  # Next.js App Router, TypeScript
│   ├── app/
│   │   ├── analysis/          # strona analizy (upload + wynik)
│   │   ├── admin/             # panel admina (wytyczne, model)
│   │   └── login/             # logowanie
│   ├── components/
│   ├── lib/
│   │   ├── api.types.ts       # generowane z OpenAPI schema
│   │   └── api.client.ts      # fetch wrapper
│   ├── hooks/
│   │   └── useAnalysis.ts     # upload + polling
│   ├── vitest.config.ts
│   ├── eslint.config.mjs
│   └── tsconfig.json          # strict: true
│
├── gateway/                   # FastAPI, JWT, Postgres
│   ├── src/
│   │   ├── domain/
│   │   │   └── user.py        # User, Role
│   │   ├── application/
│   │   │   └── auth.py        # create_token, verify_token
│   │   └── infrastructure/
│   │       ├── router.py      # FastAPI routes
│   │       ├── models.py      # SQLAlchemy models
│   │       ├── repositories.py
│   │       └── secrets.py     # Fernet encryption
│   ├── alembic/               # migracje DB
│   ├── tests/
│   └── pyproject.toml
│
├── parser/                    # FastAPI, PyMuPDF, python-docx
│   ├── src/
│   │   ├── domain/
│   │   │   └── document.py    # Document dataclass
│   │   ├── application/
│   │   │   └── extractor.py   # extract_pdf, extract_docx
│   │   └── infrastructure/
│   │       └── router.py      # POST /extract
│   ├── tests/
│   │   └── fixtures/          # test.pdf, test.docx
│   └── pyproject.toml
│
├── agent/                     # Celery, LangGraph, LangChain
│   ├── src/
│   │   ├── domain/
│   │   │   ├── analysis.py    # ThesisAnalysis, Finding, FindingSeverity
│   │   │   └── review.py      # Review, Score
│   │   ├── application/
│   │   │   ├── state.py       # AnalysisState (TypedDict)
│   │   │   ├── graph.py       # build_analysis_graph()
│   │   │   ├── nodes/
│   │   │   │   ├── structure.py
│   │   │   │   ├── methodology.py
│   │   │   │   ├── requirements.py
│   │   │   │   └── review.py
│   │   │   └── tasks.py       # Celery tasks
│   │   └── infrastructure/
│   │       ├── celery_app.py
│   │       ├── llm_factory.py # model selector
│   │       ├── vector_store.py  # RAG dla wytycznych
│   │       └── repositories.py
│   ├── tests/
│   └── pyproject.toml
│
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.override.yml  # lokalne overrides
│   ├── jenkins/
│   │   └── Jenkinsfile
│   └── sonarqube/
│       └── sonar-project.properties
│
├── docs/
│   ├── architecture.md        ← ten plik
│   └── sessions.md            ← plan sesji Claude Code
│
├── .github/
│   └── workflows/
│       ├── ci.yml             # testy + SonarQube przy PR
│       └── cd.yml             # build + deploy przy merge
│
├── .pre-commit-config.yaml
├── .env.example
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

### Przykład — warstwa domain

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
    """Pojedyncze znalezisko w analizie pracy."""
    section:     str
    description: str
    severity:    FindingSeverity
    suggestion:  str

@dataclass
class ThesisAnalysis:
    """Kompletna analiza pracy dyplomowej."""
    thesis_id:    str
    findings:     list[Finding]
    requirements: list[str]

    def critical_count(self) -> int:
        return sum(
            1 for f in self.findings
            if f.severity == FindingSeverity.CRITICAL
        )

    def is_ready_for_review(self) -> bool:
        return self.critical_count() == 0
```

### Przykład — warstwa application

```python
# agent/src/application/tasks.py
from celery import shared_task
from .graph import build_analysis_graph

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def analyze_thesis(
    self,
    thesis_id: str,
    text: str,
    guidelines: str,
) -> dict:
    """Zadanie Celery — analiza pracy dyplomowej."""
    try:
        graph = build_analysis_graph()
        result = graph.invoke({
            "thesis_id": thesis_id,
            "text": text,
            "guidelines": guidelines,
        })
        return result
    except Exception as exc:
        raise self.retry(exc=exc)
```

### Przykład — model selector

```python
# agent/src/infrastructure/llm_factory.py
from langchain_core.language_models import BaseChatModel

def get_llm() -> BaseChatModel:
    """Zwraca model LLM według MODEL_BACKEND z env."""
    match settings.model_backend:
        case "claude":
            return ChatAnthropic(
                model="claude-sonnet-4-20250514"
            )
        case "ollama":
            return ChatOllama(
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
            )
        case "openai":
            return ChatOpenAI(model="gpt-4o")
        case _:
            raise ValueError(
                f"Nieznany MODEL_BACKEND: {settings.model_backend}"
            )
```

---

## Tooling

### Python (każdy serwis)

| Narzędzie | Rola |
|---|---|
| `uv` | package manager, środowisko wirtualne |
| `ruff` | linter + formatter (zastępuje flake8 + black + isort) |
| `pyright` | static type checker (strict mode) |
| `pytest` | testy jednostkowe i integracyjne |
| `pytest-asyncio` | testy async |
| `pytest-cov` | pokrycie kodu (min 80%) |
| `structlog` | logowanie w formacie JSON |
| `pydantic-settings` | konfiguracja z env |
| `alembic` | migracje bazy danych (gateway) |
| `pre-commit` | hooki przed commitem |

### TypeScript (frontend)

| Narzędzie | Rola |
|---|---|
| `vitest` | testy jednostkowe |
| `@testing-library/react` | testy komponentów |
| `eslint` + `@typescript-eslint` | linter |
| `prettier` | formatter |
| `zod` | walidacja danych |
| `react-hook-form` | formularze |
| `swr` | data fetching i polling |
| `openapi-typescript` | generowanie typów z API schema |

---

## Zmienne środowiskowe

| Zmienna | Serwis | Opis |
|---|---|---|
| `MODEL_BACKEND` | agent | `ollama` \| `claude` \| `openai` |
| `OLLAMA_MODEL` | agent | np. `qwen3.6:14b` |
| `OLLAMA_BASE_URL` | agent | domyślnie `http://ollama:11434` |
| `ANTHROPIC_API_KEY` | agent | klucz Claude API |
| `LANGCHAIN_TRACING_V2` | agent | `true` dla LangSmith |
| `LANGCHAIN_API_KEY` | agent | klucz LangSmith |
| `LANGCHAIN_PROJECT` | agent | np. `corvus` |
| `DATABASE_URL` | gateway, agent | PostgreSQL connection string |
| `REDIS_URL` | agent, gateway | Redis connection string |
| `JWT_SECRET` | gateway | losowy string min 32 znaki |
| `JWT_ALGORITHM` | gateway | `HS256` |
| `FERNET_KEY` | gateway | klucz szyfrowania API keys |
| `SONAR_TOKEN` | CI/CD | token SonarQube |
| `SONAR_HOST_URL` | CI/CD | adres SonarQube |

Generowanie kluczy:
```bash
# FERNET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# JWT_SECRET
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## CI/CD pipeline

```
git push
  │
  ▼
GitHub Actions (ci.yml) — przy każdym PR
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
- klucze API użytkowników szyfrowane Fernetem w Postgres
- `FERNET_KEY` i `JWT_SECRET` tylko w GitHub Secrets i Jenkins Credentials
- JWT w httpOnly cookie — nie w localStorage
- każdy serwis ma non-root user w Dockerze
- Dependabot / Renovate Bot — automatyczne PR z aktualizacjami