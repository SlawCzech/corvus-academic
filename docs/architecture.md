# Corvus — architektura systemu

> Dokument referencyjny dla Claude Code i developerów.
> Aktualizuj przy każdej znaczącej zmianie architektury.
>
> Ostatnia aktualizacja: 2026-09-23 — katalog wytycznych uczelni (kontekst
> `guidelines`) i przechowywanie plików prac z retencją, ADR 0006.

---

## Stan: po Fazie 5 (RAG nad wytycznymi)

Corvus przechodzi pivot z narzędzia do analizy jednego dokumentu na platformę
mentoringową dla promotorów. Kontekst i uzasadnienie:

- [docs/adr/](adr/) — [0001](adr/0001-ai-first-mentoring-platform-pivot.md) (pivot scope'u),
  [0002](adr/0002-consolidate-services-into-app-and-agent.md) (konsolidacja serwisów),
  [0003](adr/0003-postgres-pgvector-for-persistence-and-rag.md) (Postgres/pgvector),
  [0004](adr/0004-self-hosted-default-model-with-byok.md) (model/BYOK),
  [0005](adr/0005-predefined-actions-not-open-chat.md) (predefiniowane akcje zamiast czatu),
  [0006](adr/0006-guideline-catalog-and-thesis-file-retention.md) (katalog wytycznych, pliki prac, retencja)
- [docs/specs/mentoring-platform-implementation-plan.md](specs/mentoring-platform-implementation-plan.md) — plan fazowania (Faza 0–6)
- [docs/specs/guidelines-and-thesis-files-plan.md](specs/guidelines-and-thesis-files-plan.md) — katalog wytycznych i pliki prac

**Zrobione (Faza 0):** `gateway` + `identity` + `parser` scalone w jeden serwis `app`.
**Zrobione (Faza 1):** kontekst `mentoring` — schemat Postgresa z czterema tabelami
(`students`, `thesis_drafts`, `meeting_notes`, `agent_actions`), własny lineage
Alembica i endpointy `/students/*` (roster + notatki ze spotkań).
**Zrobione (Faza 2):** pierwsza akcja AI przez całą pętlę — `propose_topic`:
`app` składa kontekst, woła `agent POST /actions`, Celery liczy graf, wynik wraca
przez polling, a akceptacja promotora ustawia `students.current_topic`. Przy okazji
naprawiona trwałość statusu: worker zapisuje `running`/`completed`/`failed` do
Postgresa (`analysis.agent_tasks`, dawniej `analyses`), zamiast czytać status z
wygasającego backendu Celery w Redisie.
**Zrobione (Faza 3):** pełny katalog sześciu akcji, upload wersji pracy
(`POST /students/{id}/drafts`, ekstrakcja in-process) i frontend mentoringowy
(`/students`, `/students/[id]`). Przejściowe endpointy (`POST /extract`, proxy
`/analysis/*`, `POST/GET /analysis` w agencie) **usunięte**.
**Zrobione (Faza 4):** BYOK — promotor zapisuje własne klucze (Claude i/lub
OpenAI, po jednym na dostawcę) w profilu i przy każdej akcji wybiera, czy
jedzie ona na któryś z nich, czy na lokalną Ollamę; bez wyboru liczy się
lokalnie ([ADR 0011](adr/0011-a-key-per-provider-chosen-per-action.md)). Klucz jest szyfrowany Fernetem, odszyfrowywany tylko w
żądaniu, które go użyje, i nigdy nie trafia do stanu grafu ani do bazy akcji.
**Zrobione (Faza 5):** wytyczne uczelniane nie są już wklejane w całości do
promptu — leżą w `analysis.guideline_chunks` pocięte na sekcje i podsekcje,
z embeddingami, a akcja dostaje te fragmenty, które dotyczą jej pracy (plus
zawsze sekcję definiującą wagi błędów). Model `nomic-embed-text` jest pobrany
i wytyczne zaingestowane: 14 chunków dla pracy licencjackiej, 18 dla
magisterskiej; zapytanie o formatowanie wyciąga inne sekcje niż o bibliografię.
Bez zaingestowanych wektorów albo bez modelu embeddingów wszystko działa jak
wcześniej — cały plik.
**Zrobione (Faza 6):** CI/CD — GitHub Actions, Jenkins, pre-commit.
**Zrobione (2026-09-23, ADR 0006):** wytyczne uczelni są danymi, a nie plikami
w obrazie agenta — kontekst `guidelines` w `app` (uczelnie → zestawy per typ
pracy → wersje; opublikowana wersja jest niezmienna, akcja zapisuje, według
której wersji ją oceniono). Promotor wybiera zestaw dla studenta; rubryka
opublikowanej wersji jedzie w kontekście akcji, a agent bez zmian pomija wtedy
własne wytyczne. Wgrany plik pracy jest przechowywany (port `FileStore`,
`bytea` w schemacie kontekstu), promotor akceptuje wersję finalną, a codzienny
sweep usuwa treść i plik pozostałych wersji po 30 dniach i wszystkich po 150
dniach od zakończenia opieki; wiersz wersji zostaje jako ślad.

---

## Cel systemu

Corvus to aplikacja webowa wspomagająca promotorów i recenzentów w prowadzeniu
studentów przez cykl pracy dyplomowej: notatki ze spotkań, propozycja i ocena
tematu, ocena metodologii, wykrywanie zmian między wersjami, recenzja końcowa.

Projekt służy jednocześnie jako platforma edukacyjna — od 2026-09-05 nacisk
przesunięty z DDD/mikroserwisów na wzorce budowy aplikacji AI (LangGraph,
tool use, structured output, BYOK, ewaluacje).

---

## Bounded Contexts (DDD)

Konteksty są rozdzielone na poziomie pakietów Pythona i schematów Postgresa,
nie na poziomie sieci — `app` to jeden proces obsługujący kilka kontekstów.
Referencje między kontekstami to gołe UUID bez kluczy obcych.

| Context | Lokalizacja | Schemat DB | Odpowiedzialność |
|---|---|---|---|
| identity | `app/src/identity/` | `identity` | autentykacja, użytkownicy, role/permissions, audyt, klucze API |
| document | `app/src/document/` | — | ekstrakcja tekstu z PDF i DOCX (bezstanowa) |
| mentoring | `app/src/mentoring/` | `mentoring` | studenci, notatki ze spotkań, wersje draftów (z plikami i retencją), log akcji AI |
| guidelines | `app/src/guidelines/` | `guidelines` | katalog wytycznych uczelni: zestawy, wersje, rubryki, progi, oryginały zarządzeń |
| analysis | `agent/src/` | `analysis` | orkiestracja LangGraph, węzły analizy |
| review | `agent/src/` | `analysis` | generowanie recenzji, ton, ocena punktowa |

---

## Serwisy (docker-compose)

| Serwis | Port | Stack | Opis |
|---|---|---|---|
| frontend | 3000 | Next.js, TypeScript | interfejs webowy |
| app | 8000 | FastAPI, Postgres | auth/użytkownicy/role/audyt + studenci, wersje pracy, akcje AI |
| agent | 8002 | FastAPI | HTTP API — przyjmowanie akcji i ich status |
| agent-worker | — | Celery | worker wykonujący graf LangGraph (ten sam obraz co `agent`) |
| ollama | 11434 | Ollama | lokalne modele LLM |
| redis | 6379 | Redis | broker Celery + blacklist refresh tokenów |
| postgres | 5432 | PostgreSQL 16 + pgvector | schematy identity, mentoring, guidelines, analysis (w tym embeddingi wytycznych) |
| flower | 5555 | Celery Flower | monitoring kolejki |
| jenkins | 8080 | Jenkins LTS | CI/CD pipeline (jeszcze nieskonfigurowany — Faza 6) |
| sonarqube | 9000 | SonarQube CE | analiza jakości kodu (jeszcze nieskonfigurowany — Faza 6) |

`agent` i `agent-worker` współdzielą ten sam obraz Dockera —
`agent` uruchamia serwer FastAPI (przyjmuje żądania, zapisuje rekord
w Postgres, wrzuca zadanie do Celery), `agent-worker` uruchamia
`celery worker` i faktycznie wykonuje graf LangGraph.

Jedyny podział sieciowy, jaki został: szybkie, synchroniczne CRUD (`app`)
kontra wolne, asynchroniczne wywołania LLM (`agent`) — patrz ADR 0002.

---

## Przepływ danych

```
Użytkownik (przeglądarka)
  │
  ▼
frontend :3000  (Next.js route handlers jako proxy do app, jedno APP_URL)
  │  /students, /students/[id] — roster, wersje pracy, notatki, akcje AI
  ▼
app :8000
  │
  ├──► /auth/*, /users/*, /admin/*, /settings/*   — obsługiwane IN-PROCESS
  │      login, refresh (httpOnly cookie), rejestracja,
  │      role/permissions, audyt logowań, szyfrowanie kluczy API (Fernet)
  │
  ├──► /students/*  — roster i notatki ze spotkań, IN-PROCESS
  │      POST/GET /students, GET/PATCH /students/{id},
  │      POST/GET /students/{id}/meeting-notes
  │      widoczność: promotor widzi swoich, admin wszystkich
  │      (VIEW_ALL_STUDENTS); cudzy student to 404, nie 403
  │
  ├──► /students/{id}/drafts  — wersje pracy
  ├──► /students/{id}/fragments, /parts, /timeline  — fragmenty w rundach, oś czasu
  ├──► /reviews  — jednorazowa recenzja i promocja do studenta (ADR 0017)
  │      POST   → limit 25 MB, format sprawdzony po zawartości, ekstrakcja
  │               in-process (PyMuPDF / python-docx); plik i tekst zapisane
  │               jako wersja N+1; nowa wersja zdejmuje akceptację
  │      GET    → lista wersji (metadane, podgląd, akceptacja, data usunięcia)
  │      GET    .../{draft_id}/file → oryginał jako załącznik
  │      POST/DELETE .../{draft_id}/accept → wersja finalna / cofnięcie
  │      DELETE .../{draft_id} → usunięcie treści i pliku; wiersz zostaje
  │      Retencja: sweep w lifespan `app` raz na dobę (i `make purge-drafts`):
  │      niezaakceptowane wersje 30 dni po akceptacji, wszystkie 150 dni po
  │      graduated/archived
  │
  ├──► /guidelines/*  — katalog wytycznych, IN-PROCESS
  │      GET  → zestawy, wersje, oryginał zarządzenia (promotor: bez szkiców)
  │      /guidelines/admin/* (MANAGE_GUIDELINES) → uczelnie, zestawy,
  │               szkic → edycja → publikacja (poprzednia: superseded)
  │      PATCH /students/{id} {guideline_set_id} → wybór zestawu dla studenta
  │
  ├──► /students/{id}/actions  — akcje AI
  │      POST   → składa kontekst (mentoring/application/context.py),
  │               zapisuje wiersz agent_actions (pending),
  │               woła agent POST /actions, zapisuje task_id
  │               409, jeśli rekord studenta nie ma jeszcze tego, czego
  │               akcja wymaga (np. pytania na obronę bez wgranej pracy)
  │      GET    → polling: dopóki akcja nie jest terminalna, dociąga
  │               status z agent GET /actions/{task_id}
  │      PATCH .../accept → propose_topic ustawia current_topic,
  │               draft_meeting_note zapisuje notatkę z source_action_id
  │
  │      Kontekst składa WYŁĄCZNIE `app` — agent nigdy nie oddzwania po
  │      dane, więc zadanie workera nie zależy od tego, czy `app` żyje.
  │      Każda akcja pobiera tylko to, czego potrzebuje: check_progress
  │      dwa ostatnie drafty, propose_topic żadnego.
  │
  └──► agent :8002 (HTTP API) — POST /actions, GET /actions/{task_id}
         │
         ▼
       agent :8002
         zapis wiersza analysis.agent_tasks (status=pending) PRZED wysyłką —
         task_id generuje wołający, więc worker nie wyprzedzi wiersza,
         który ma zaktualizować
         Celery send_task(...) → zwraca task_id natychmiast
         │
         ▼
       agent-worker (Celery worker)
         zapisuje status do Postgresa: running → completed | failed
         │
         ▼
       model selector (llm_factory): klucz wybranego dostawcy (ContextVar,
       tylko na czas tego przebiegu) → Claude/OpenAI; bez dostawcy → Ollama
         │
         ▼
       LangGraph — graf zależny od typu akcji (build_action_graph):
         generate_review      [struktura] → [metodologia] → [wymogi] → [recenzja]
                              (mode="review_only" → sama recenzja)
         propose_topic        [propose_topic]
         defence_questions    [defence_questions]     — 3 pytania na obronę
         review_fragment      [review_fragment]       — podsumowanie i łagodny feedback
                                                        do fragmentu (ADR 0014)
         check_progress       [check_progress]        — porównanie 2 wersji
         evaluate_methodology [analyze_methodology]   — ten sam węzeł, osobno
         draft_meeting_note   [draft_meeting_note]
         draft_student_email  [draft_student_email]
       Nieznany typ akcji → 422 przy żądaniu, zamiast zadania, które i tak by padło.
       Gdy student ma wybrany zestaw, rubrykę opublikowanej wersji wkłada do
       kontekstu `app` (klucz `guidelines`), a `input_ref` akcji zapisuje
       `guideline_version_id`. W przeciwnym razie wytyczne uczelniane dokłada
       `agent` (dane statyczne, których jest właścicielem) — nie cały plik,
       tylko sekcje wyszukane pod tę pracę (pgvector, `nomic-embed-text`,
       768 wymiarów) plus sekcja definiująca wagi błędów, zawsze.
       Embeddingi liczy `EMBEDDING_BASE_URL`, który nie musi być tym samym
       serwerem co modele czatu — serwer czatu bywa bez embeddingów.
       Brak ingestii albo brak modelu → fallback na cały dokument.

       Stan grafu (ActionState) jest wspólny dla wszystkich akcji: to, co
       specyficzne dla akcji, siedzi w `context`, dzięki czemu nowa akcja to
       nowy węzeł, a nie nowy schemat stanu.
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
       Postgres  (analysis.agent_tasks: status, result, error)
         result jest przycięty — tekst pracy i wytyczne to wejście,
         nie wynik, i nie trafiają do JSONB ani do odpowiedzi HTTP
  ▼
frontend (polling GET /api/students/{id}/actions/{actionId} co 3s)
  wyświetla wynik i — gdzie to ma sens — przycisk akceptacji
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
│   │   ├── students/            # lista studentów + karta studenta
│   │   │   └── [id]/             # temat, wersje pracy, notatki, akcje AI
│   │   ├── guidelines/           # katalog wytycznych + strona wersji
│   │   ├── admin/                # panel admina
│   │   │   ├── users/            # zarządzanie użytkownikami
│   │   │   ├── guidelines/       # katalog: uczelnie, zestawy, szkice, publikacja
│   │   │   └── login-events/     # audyt logowań
│   │   ├── profile/               # profil użytkownika, zmiana hasła
│   │   └── api/                    # route handlers — proxy do app
│   │       ├── auth/{login,logout,refresh}/
│   │       ├── students/           # + [id]/{drafts,meeting-notes,actions}
│   │       ├── users/
│   │       └── admin/
│   ├── components/
│   │   └── students/            # StudentForm, StudentDetail, ActionPanel,
│   │                              ActionResultView
│   ├── lib/                      # api.client, api.types, appProxy (APP_URL)
│   ├── hooks/useAction.ts        # trigger + polling jednej akcji
│   ├── proxy.ts                 # ochrona /admin i /students (cookie JWT)
│   ├── vitest.config.ts
│   ├── eslint.config.mjs
│   └── tsconfig.json            # strict: true
│
├── app/                        # FastAPI, Postgres — identity + document + mentoring
│   ├── main.py                  # montuje routery: identity, mentoring, health
│   ├── alembic_identity.ini
│   ├── alembic_identity/        # lineage migracji dla schematu `identity`
│   ├── alembic_mentoring.ini
│   ├── alembic_mentoring/       # lineage migracji dla schematu `mentoring`
│   ├── alembic_guidelines.ini
│   ├── alembic_guidelines/      # lineage migracji dla schematu `guidelines`
│   │                              (entrypoint.sh podnosi wszystkie trzy, po kolei)
│   ├── scripts/                 # seed_admin, seed_guidelines (+ seed_data/),
│   │                              purge_drafts (sweep retencji, --now)
│   ├── src/
│   │   ├── identity/
│   │   │   ├── domain/user.py       # Role, Permission, User, UserRegistration
│   │   │   │                          (email-validator, uprawnienia per-rola)
│   │   │   ├── application/
│   │   │   │   ├── auth.py          # create/verify access+refresh tokens (JWT)
│   │   │   │   └── user_service.py  # rejestracja, uwierzytelnianie, bcrypt
│   │   │   └── infrastructure/
│   │   │       ├── router.py        # /auth/*, /users/*, /admin/*, /settings/*
│   │   │       ├── models.py        # SQLAlchemy — UserModel, LoginEventModel
│   │   │       ├── repositories.py
│   │   │       ├── secrets.py       # Fernet encryption kluczy API
│   │   │       ├── token_store.py   # RevokedTokenStore (Redis, revocation)
│   │   │       └── limiter.py       # rate limiting na /auth/login
│   │   ├── mentoring/
│   │   │   ├── domain/
│   │   │   │   ├── student.py       # Student, MeetingNote, StudentStatus,
│   │   │   │   │                      ThesisType
│   │   │   │   └── action.py        # AgentAction, ActionType, ActionStatus
│   │   │   ├── domain/draft.py     # ThesisDraft (wersje pracy)
│   │   │   ├── application/
│   │   │   │   ├── student_service.py  # Caller (kto pyta + czy widzi wszystko),
│   │   │   │   │                         reguła własności, use case'y
│   │   │   │   ├── draft_service.py # upload → ekstrakcja → wersja N+1
│   │   │   │   ├── context.py       # co model widzi — jedna funkcja na akcję
│   │   │   │   ├── agent_client.py  # HTTP do agenta (/actions)
│   │   │   │   └── action_service.py   # trigger → polling → accept
│   │   │   └── infrastructure/
│   │   │       ├── router.py        # /students/*, .../drafts, .../actions
│   │   │       ├── models.py        # StudentModel, ThesisDraftModel,
│   │   │       │                      MeetingNoteModel, AgentActionModel
│   │   │       └── repositories.py
│   │   ├── guidelines/
│   │   │   ├── domain/catalog.py    # University, GuidelineSet, GuidelineVersion
│   │   │   │                          (szkic → published → superseded), Thresholds
│   │   │   ├── application/         # catalog.py (odczyt), admin_service.py
│   │   │   └── infrastructure/      # orm, repositories, router, schemas,
│   │   │                              dependencies (MANAGE_GUIDELINES)
│   │   ├── document/
│   │   │   ├── document.py          # Document dataclass
│   │   │   └── extractor.py         # extract, detect_verified_format (magic bytes)
│   │   └── shared/
│   │       ├── files.py              # port FileStore + StoredFile
│   │       ├── sql_file_store.py     # adapter Postgres (bytea), FileBlobColumns
│   │       ├── downloads.py          # limit uploadu, odpowiedź-załącznik
│   │       ├── settings.py           # scalona konfiguracja (identity + gateway)
│   │       ├── database.py           # jeden async engine + session factory
│   │       ├── health.py             # GET /health (status agenta)
│   │       ├── logging.py            # structlog JSON
│   │       └── middleware.py         # request_id
│   ├── tests/{test_identity,test_mentoring,test_guidelines,test_document,test_shared}/
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
│   │   ├── domain/action.py     # ActionType, TaskStatus (słownik akcji i statusów)
│   │   ├── application/
│   │   │   ├── state.py         # ActionState (TypedDict) — wspólny dla wszystkich
│   │   │   │                      akcji; co specyficzne, siedzi w `context`
│   │   │   ├── graph.py         # build_action_graph(action_type) +
│   │   │   │                      build_analysis_graph(mode="full"|"review_only")
│   │   │   ├── guidelines.py    # loader wytycznych uczelnianych/promotora
│   │   │   ├── json_output.py   # wspólne parsowanie odpowiedzi modelu
│   │   │   ├── nodes/
│   │   │   │   ├── structure.py
│   │   │   │   ├── methodology.py
│   │   │   │   ├── requirements.py
│   │   │   │   ├── review.py
│   │   │   │   ├── propose_topic.py
│   │   │   │   ├── defence_questions.py
│   │   │   │   ├── check_progress.py
│   │   │   │   ├── draft_meeting_note.py
│   │   │   │   └── draft_student_email.py
│   │   │   ├── prompts/          # system prompty per węzeł + wytyczne
│   │   │   └── tasks.py          # Celery: run_action
│   │   └── infrastructure/
│   │       ├── api/
│   │       │   ├── router.py    # POST /actions, GET /actions/{task_id}
│   │       │   └── auth.py      # lokalna weryfikacja JWT (bez wołania identity)
│   │       ├── celery_app.py
│   │       ├── llm_factory.py   # model selector
│   │       ├── models.py        # SQLAlchemy — AgentTaskModel
│   │       ├── task_status.py   # zapis statusu z workera (sync → asyncio.run)
│   │       └── repositories.py
│   ├── prompts/                  # pliki wytycznych (guidelines)
│   ├── tests/
│   └── pyproject.toml
│
├── infra/
│   ├── docker-compose.yml        # 10 serwisów: frontend, app, agent, agent-worker,
│   │                                flower, ollama, redis, postgres, jenkins, sonarqube
│   └── docker-compose.override.yml  # lokalne overrides (hot-reload, DEBUG)
│
├── docs/
│   ├── architecture.md          ← ten plik
│   ├── sessions.md               # plan sesji Claude Code + stan projektu
│   ├── technical-debt.md         # dług techniczny
│   └── specs/                    # specyfikacje pojedynczych funkcji
│
├── .github/workflows/            # jeszcze nieutworzone — Faza 6
├── .pre-commit-config.yaml       # jeszcze nieutworzony — Faza 6
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

`app/src/document/` jest wyjątkiem świadomym: nie ma warstwy `domain/`, bo nie
ma własnej logiki biznesowej — to cienka warstwa nad PyMuPDF/python-docx,
wołana in-process przy uploadzie wersji pracy.

### Przykład — warstwa domain (identity)

```python
# app/src/identity/domain/user.py
class Role(StrEnum):
    ADMIN = "admin"
    PROMOTOR = "promotor"

class Permission(StrEnum):
    MANAGE_USERS = "manage_users"
    VIEW_ALL_ANALYSES = "view_all_analyses"
    SUBMIT_ANALYSIS = "submit_analysis"
    MANAGE_STUDENTS = "manage_students"
    VIEW_ALL_STUDENTS = "view_all_students"

_ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.PROMOTOR: frozenset(
        {Permission.SUBMIT_ANALYSIS, Permission.MANAGE_STUDENTS}
    ),
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

### Przykład — składanie kontekstu akcji

```python
# app/src/mentoring/application/context.py
def assemble_check_progress_context(
    student: Student,
    latest_drafts: Sequence[ThesisDraft],
    detail: str | None = None,
) -> dict[str, Any]:
    if len(latest_drafts) < 2:
        raise MissingContextError("Progress needs two uploaded versions to compare")
    current, previous = latest_drafts[0], latest_drafts[1]
    return {
        "current_text": current.text,
        "current_version": current.version_number,
        "previous_text": previous.text,
        "previous_version": previous.version_number,
        "current_topic": student.current_topic,
        "detail": detail,
    }
```

Jedna funkcja na typ akcji, czysta i testowalna bez bazy. To także szew, w
którym przyszły agent czatowy podniesie te same funkcje jako narzędzia.
Kontekst składa wyłącznie `app`; `agent` dokłada tylko wytyczne uczelniane,
bo to jego własne dane statyczne.

### Przykład — model selector

```python
# agent/src/infrastructure/llm_factory.py
def get_llm(model: str) -> BaseChatModel:
    match settings.model_backend:
        case "claude":
            return ChatAnthropic(model="claude-sonnet-5-5")
        case "ollama":
            return ChatOllama(model=model, base_url=settings.ollama_base_url)
        case "openai":
            return ChatOpenAI(model="gpt-6.1-sol")
        case _:
            raise ValueError(f"Nieznany MODEL_BACKEND: {settings.model_backend}")
```

### Tracing — Langfuse, self-hosted

Każdy przebieg grafu idzie z `config` z [`tracing.run_config`](../agent/src/infrastructure/tracing.py):
nazwa `action:<typ>`, tagi (typ akcji, model), sesja = student. LangGraph podaje ten
config każdemu węzłowi, a `llm.invoke` w węźle podnosi callback z kontekstu —
żaden węzeł nie wie, że jest śledzony. W Langfuse widać drzewo
`action:generate_review` → węzeł → `ChatOllama` z czasem i promptem każdego wywołania.

- Osobny projekt compose ([infra/langfuse/](../infra/langfuse/docker-compose.yml)),
  `make langfuse-up`, UI na `localhost:3100`. Włączany trzema zmiennymi `LANGFUSE_*`
  w `.env`; bez nich callbacku po prostu nie ma.
- Self-hosted, nie LangSmith: prompt niesie tekst pracy studenta.
- Awaria Langfuse nigdy nie wywraca akcji — brak callbacku, ostrzeżenie w logu.

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
| `RateLimit` (własny) | rate limiting (identity — logowanie, zmiana hasła, prośby o dostęp) |

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
| `ENVIRONMENT` | app | `local` \| `production` — steruje flagą `Secure` na cookie, log levelem |
| `DATABASE_URL` | app, agent | PostgreSQL connection string |
| `REDIS_URL` | agent, app | broker Celery + refresh token store |
| `JWT_SECRET` / `JWT_ALGORITHM` | app, agent | wspólny sekret — każdy serwis weryfikuje JWT lokalnie |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | app | TTL tokenów |
| `FERNET_KEY` | app | szyfrowanie kluczy API użytkowników |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | app | seed pierwszego konta admina (wymagane, min. 12 znaków hasła) |
| `AGENT_URL` | app | adres serwisu agent (`http://agent:8002`) |
| `SONAR_TOKEN` / `SONAR_HOST_URL` | CI/CD | jeszcze nieużywane — Faza 6 |

Generowanie kluczy:
```bash
# FERNET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# JWT_SECRET
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## CI/CD pipeline

Testy, lint i typy sprawdza GitHub Actions przy każdym PR i pushu na `main`.
Jenkins tylko wdraża to, co już przeszło.

```
git push / PR
  │
  ▼
GitHub Actions (.github/workflows/ci.yml)
  ├── app         uv sync --frozen · ruff · pyright src · pytest
  ├── agent       uv sync --frozen · ruff · pyright src · pytest
  ├── frontend    npm ci · eslint · tsc --noEmit · vitest
  ├── migrations  wszystkie trzy lineage'y na pustej bazie
  │               (obraz pgvector/pgvector:pg16 — migracja 0004 go wymaga)
  └── sonarqube   po przejściu trzech pierwszych; pomijany, gdy nie ma
                  SONAR_TOKEN (serwer jest self-hosted)
  │
  ▼ (merge do main)
  │
Jenkins (infra/jenkins/Jenkinsfile)
  ├── Checkout + .env z Jenkins credentials
  ├── docker compose build
  ├── Migracje (identity, mentoring, analysis) PRZED startem kontenerów
  ├── docker compose up -d --remove-orphans
  └── Healthcheck /health (raportuje też stan agenta), do 150 s
```

`pyright` w CI sprawdza **`src`**, nie testy: w testach zostaje ok. 250 błędów
`reportUnknownMemberType` na `TestClient`/`httpx` (patrz
[technical-debt.md](technical-debt.md)). Kod produkcyjny obu serwisów jest
czysty w trybie strict i CI tego pilnuje.

Lokalnie te same reguły w skróconej formie:

```bash
uvx pre-commit install    # ruff --fix, eslint, higiena plików, detect-private-key
```

Hooki celowo nie uruchamiają `pytest` ani `pyright` — 55 s na commit to hook,
który ludzie wyłączają przez `--no-verify`. Od tego jest CI.

---

## Bezpieczeństwo

- `.env` zawsze w `.gitignore` — nigdy w repo
- JWT_SECRET współdzielony przez `app` i `agent` — każdy weryfikuje token
  lokalnie, bez wywołania sieciowego
- endpointy `/internal/*` (nieuwierzytelniony lookup użytkownika i introspekcja
  tokenu) **usunięte w Fazie 0** — ich jedyną ochroną była topologia sieci
  (gateway ich nie proxował); po scaleniu na publicznym porcie byłyby dziurą.
  Nic ich nie wołało
- access token (12 h, `ACCESS_TOKEN_EXPIRE_MINUTES=720`) + refresh token (30 dni) w httpOnly cookie,
  `samesite=strict`, ograniczony do path `/auth/refresh`; flaga `Secure`
  zależna od `ENVIRONMENT` (włączona tylko na produkcji, żeby lokalny HTTP działał)
- access i refresh tokeny odwoływalne przez `RevokedTokenStore` (Redis, JTI
  blacklist): `/auth/logout` odwołuje oba, każdy na tyle, ile jeszcze byłby
  ważny, a `get_current_user` sprawdza listę przy każdym żądaniu (fail-open,
  gdy Redis leży — patrz `technical-debt.md`)
- klucze API użytkowników szyfrowane Fernetem w Postgres; w kolejce Celery klucz
  jedzie zaszyfrowany kluczem wyprowadzonym z `JWT_SECRET` i otwiera go dopiero
  worker ([ADR 0012](adr/0012-seal-the-provider-key-for-the-task-queue.md))
- każdy serwis ma non-root user w Dockerze
- audyt logowań (`LoginEventModel`) — IP, user-agent, sukces/porażka
- rate limiting na `/auth/login` (`identity/infrastructure/limiter.py`, okno przesuwne per klient)
- Dependabot / Renovate Bot — **jeszcze nieskonfigurowane**
