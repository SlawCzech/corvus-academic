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

### 3.1 Bounded Contexts (DDD)

```
document/     — parsowanie i ekstrakcja tekstu z PDF/DOCX
analysis/     — agent LangGraph, węzły analizy, orchestracja
review/       — generowanie recenzji, ocena, raport końcowy
identity/     — autentykacja, użytkownicy, role, klucze API
```

### 3.2 Microservices (docker-compose)

| Serwis | Port | Stack | Bounded Context |
|---|---|---|---|
| frontend | 3000 | Next.js, TypeScript | — |
| gateway | 8000 | FastAPI, JWT | identity |
| parser | 8001 | FastAPI, PyMuPDF | document |
| agent | 8002 | LangGraph, Celery | analysis + review |
| ollama | 11434 | Ollama | — |
| redis | 6379 | Redis Streams | — |
| postgres | 5432 | PostgreSQL + Alembic | — |
| flower | 5555 | Celery Flower | — |
| jenkins | 8080 | Jenkins | — |
| sonarqube | 9000 | SonarQube CE | — |

### 3.3 Przepływ danych

```
Użytkownik
  → frontend (upload PDF/DOCX)
  → gateway (JWT auth, routing)
  → parser (ekstrakcja tekstu)
  → gateway (task_id zwrócony natychmiast)
  → Celery worker (zadanie async)
  → Redis Streams (broker)
  → LangGraph agent (węzły sekwencyjne)
      → [Struktura] → [Metodologia] → [Wymogi RAG] → [Recenzja]
  → model selector
      → Ollama (lokalny) LUB Claude/OpenAI API (cloud)
  → Postgres (zapis raportu)
  → frontend (polling → wyświetlenie raportu)
```

### 3.4 Model selector

Przełączanie modelu przez zmienną środowiskową lub klucz API w UI:

```python
# agent/infrastructure/llm_factory.py
match settings.model_backend:
    case "ollama":   return ChatOllama(model=settings.ollama_model)
    case "claude":   return ChatAnthropic(model="claude-sonnet-4-20250514")
    case "openai":   return ChatOpenAI(model="gpt-4o")
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
├── gateway/
│   ├── src/
│   │   ├── domain/           # encje, value objects, reguły
│   │   ├── application/      # use cases, DTOs
│   │   └── infrastructure/   # FastAPI routes, DB, JWT
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
│
├── parser/
│   ├── src/
│   │   ├── domain/
│   │   ├── application/
│   │   └── infrastructure/   # PyMuPDF, python-docx
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
│
├── agent/
│   ├── src/
│   │   ├── domain/
│   │   │   ├── analysis.py   # encje: ThesisAnalysis, Finding
│   │   │   └── review.py     # encje: Review, Score
│   │   ├── application/
│   │   │   ├── graph.py      # definicja grafu LangGraph
│   │   │   ├── nodes/        # węzły: structure, methodology, requirements, review
│   │   │   └── tasks.py      # Celery tasks
│   │   └── infrastructure/
│   │       ├── llm_factory.py
│   │       ├── vector_store.py  # RAG dla wytycznych
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
- `alembic` (migracje DB, tylko gateway)

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

### 6.1 GitHub Actions — CI (pull request)

```yaml
# .github/workflows/ci.yml
name: CI
on: [pull_request]
jobs:
  test-python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv run pytest --cov-report=xml
      - run: uv run ruff check .
      - run: uv run pyright

  test-typescript:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: npm ci && npm run typecheck && npm test

  sonarqube:
    needs: [test-python, test-typescript]
    runs-on: ubuntu-latest
    steps:
      - uses: SonarSource/sonarqube-scan-action@v2
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
```

### 6.2 Jenkinsfile — CD (deploy)

```groovy
// infra/jenkins/Jenkinsfile
pipeline {
    agent any
    environment {
        GHCR_TOKEN = credentials('github-token')
        ENV_FILE   = credentials('env-production')
    }
    stages {
        stage('Pull images') {
            steps {
                sh 'echo $GHCR_TOKEN | docker login ghcr.io -u USERNAME --password-stdin'
                sh 'docker-compose -f infra/docker-compose.yml pull'
            }
        }
        stage('Deploy') {
            steps {
                sh 'docker-compose -f infra/docker-compose.yml up -d --remove-orphans'
            }
        }
        stage('Healthcheck') {
            steps {
                sh 'sleep 10 && curl -f http://localhost:8000/health'
            }
        }
    }
    post {
        failure { mail to: 'admin@example.com', subject: 'Deploy failed' }
    }
}
```

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
from celery import shared_task
from .graph import build_analysis_graph

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def analyze_thesis(self, thesis_id: str, text: str, guidelines: str) -> dict:
    try:
        graph  = build_analysis_graph()
        result = graph.invoke({"thesis_id": thesis_id,
                               "text": text,
                               "guidelines": guidelines})
        return result
    except Exception as exc:
        raise self.retry(exc=exc)
```

### Reguła: zależności idą tylko do wewnątrz

```
infrastructure → application → domain
                               ↑ zero importów z zewnątrz
```

---

## 8. Bezpieczeństwo kluczy API

```python
# gateway/src/infrastructure/secrets.py
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
- `FERNET_KEY` generowany raz: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

---

## 9. Kolejność implementacji (sugerowana)

### Faza 1 — rdzeń AI (tydzień 1–2)
- [ ] Agent LangGraph z jednym węzłem (Struktura)
- [ ] Integracja z Claude API przez LangChain
- [ ] LangSmith tracing (LANGCHAIN_TRACING_V2=true)
- [ ] Testy jednostkowe węzła (pytest)

### Faza 2 — dokument i kolejkowanie (tydzień 3–4)
- [ ] Serwis parser (PyMuPDF + python-docx)
- [ ] Celery + Redis Streams
- [ ] Pozostałe węzły LangGraph
- [ ] Podmiana modelu: Ollama lokalnie

### Faza 3 — API i baza (tydzień 5–6)
- [ ] Gateway FastAPI + JWT
- [ ] Postgres + Alembic migracje
- [ ] Secret vault dla kluczy API
- [ ] Healthcheck endpoints

### Faza 4 — frontend (tydzień 7–8)
- [ ] Next.js upload + polling statusu
- [ ] Panel administracyjny (wytyczne, model selector)
- [ ] Flower UI integracja

### Faza 5 — CI/CD i jakość (tydzień 9–10)
- [ ] GitHub Actions (CI: testy + SonarQube)
- [ ] Jenkins (CD: deploy)
- [ ] Pre-commit hooks
- [ ] Dependabot / Renovate Bot
- [ ] README + dokumentacja API (FastAPI autodocs)

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
DATABASE_URL=postgresql://user:pass@postgres:5432/thesis_reviewer

# Redis
REDIS_URL=redis://redis:6379/0

# Bezpieczeństwo
FERNET_KEY=                              # wygeneruj: patrz sekcja 8
JWT_SECRET=                              # losowy string min 32 znaki
JWT_ALGORITHM=HS256

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
