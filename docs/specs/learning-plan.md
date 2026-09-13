# Corvus — plan poznawczy: architektura, agent, deploy, front

> Status: aktywny · utworzony 2026-09-06 · zaktualizowany 2026-09-13 ·
> robota na kilka dni i kilka sesji.
> Ten plik NIE jest planem implementacji — od tego jest
> [mentoring-platform-implementation-plan.md](mentoring-platform-implementation-plan.md)
> (wszystkie sześć faz zamkniętych). Ten jest planem **zrozumienia tego, co już
> działa**, plus jedną nową robotą (front).
>
> Powiązane: [docs/architecture.md](../architecture.md) (aktualne, 568 linii — mapa terenu) ·
> [docs/adr/](../adr/) (dlaczego tak, a nie inaczej) ·
> [docs/technical-debt.md](../technical-debt.md) (co świadomie zostało odłożone)

---

## Jak korzystać z tego planu

**Metoda: trace-driven, nie plik po pliku.** Największe ryzyko przy „chcę
zrozumieć" to przeczytanie katalogu alfabetycznie i poczucie, że się rozumie.
Każdy blok poniżej prowadzi jedno prawdziwe żądanie przez warstwy, z logami
dwóch serwisów obok siebie.

**Zasada: każdy blok kończy się artefaktem.** „Przeczytałem" nie jest
weryfikowalne. „Narysowałem sekwencję i zgadza się z logami" jest.

**Szablon promptu na start sesji** (konwencja z [docs/sessions.md](../sessions.md)):

```
Read CLAUDE.md and docs/specs/learning-plan.md.

Robimy Blok [A / B1 / B2 / C / D].
Poprzednio: [co zostało zrobione, jaki artefakt powstał]

Zacznij od [pierwszy plik ze ścieżki czytania]. Tłumacz w miarę czytania,
zatrzymuj się na pytaniach z sekcji „Pytania otwarte".
```

---

## Stan wyjściowy (zweryfikowany 2026-09-13)

| Co | Stan |
|---|---|
| Gałąź | `main`, czysto, HEAD `15fc21d` (4 commity ponad `origin/main` — niewypchnięte) |
| Testy | `app` 220 passed · `agent` 177 passed · `frontend` 44 passed |
| Kontenery | `app`, `agent`, `agent-worker`, `postgres`, `redis`, `ollama` healthy; `frontend` raportuje `unhealthy` — Next w trybie standalone bindje się na `$HOSTNAME`, a healthcheck puka na `localhost` (strona działa, probe kłamie) |
| Wektory | `analysis.guideline_chunks`: 14 chunków `bachelor`, 18 `master_article`, model `nomic-embed-text` |
| Dane | 1 studentka, 5 akcji, 5 draftów, 1 user (admin) — prawdziwa praca magisterska w bazie, dobra do tracowania |

---

## Mapa: co robi każdy serwis (ściąga na cały plan)

| Serwis | Port | Rola w jednym zdaniu |
|---|---|---|
| `frontend` | 3000 | Next 16 + React 19 + Tailwind 4; pollinguje akcje przez SWR |
| `app` | 8000 | wszystko szybkie i synchroniczne — auth, roster, notatki, ekstrakcja PDF/DOCX **in-process**, cały cykl życia akcji; właściciel schematów `identity` i `mentoring` |
| `agent` | 8002 | cienka fasada nad kolejką: przyjmuje `POST /actions`, wrzuca do Celery, oddaje `task_id`; właściciel schematu `analysis` |
| `agent-worker` | — | ten sam obraz co `agent` (dosłownie ten sam — `image: corvus-agent` w obu serwisach), ale `celery worker` — **to on liczy graf**; nie wystawia HTTP, więc ma healthcheck przez `celery inspect ping` |
| `redis` | 6379 | broker Celery (result backend istnieje, ale status i tak żyje w Postgresie — Redis wygasa) |
| `postgres` | 5432 | trzy schematy, trzy lineage Alembica, pgvector |
| `ollama` | 11434 | modele czatu **i** embeddingów — pod dwoma różnymi URL-ami, i to nie przypadek |
| `flower` | 5555 | podgląd kolejki |
| `jenkins` / `sonarqube` | 8080 / 9000 | deploy / jakość (sonar nieskonfigurowany) |

---

# Blok A — architektura: dwa serwisy i granica między nimi

**Sesje: 1**

### Cel

Odpowiedzieć na pytanie: dlaczego dwa serwisy, a nie jeden albo pięć, i co
dokładnie przechodzi przez tę granicę.

### Ścieżka czytania (w kolejności wykonania, nie alfabetycznej)

1. `infra/docker-compose.yml` — kto z kim gada, kto ma healthcheck
2. `app/main.py` + `app/src/shared/settings.py` — co `app` montuje
3. `app/src/mentoring/infrastructure/router.py` (599 linii — jedyny duży plik po stronie `app`)
4. `app/src/mentoring/application/context.py` → `app/src/mentoring/application/agent_client.py` — **to jest granica**
   (a w niej `app/src/document/outline.py` — mapa dokumentu liczona nad całym
   tekstem, bez modelu: najostrzejszy dowód na to, że kontekst powstaje tutaj)
5. `agent/src/infrastructure/api/router.py` — druga strona
6. `app/src/mentoring/application/action_service.py` — kto co robi z wynikiem

### Pojęcia, które mają zostać w głowie

- **Kontekst jest składany w całości w `app` i wysyłany jednym strzałem; agent
  nigdy nie oddzwania po dane.** To jest THE decyzja tej architektury.
- **`app` posiada cykl życia akcji, agent posiada tylko przebieg grafu.** Wiersz
  w `mentoring.agent_actions` powstaje przed wysyłką; agent zna tylko `task_id`.
- **Trzy schematy = trzy lineage Alembica.** `identity` i `mentoring` w `app/`,
  `analysis` w `agent/`. Cross-context referencje (`promotor_id`, `uploaded_by`)
  to gołe UUID bez FK — świadomie.

### Trade-off do nazwania na głos

Podział sieciowy kupuje **availability** (worker robi swoje, gdy `app` leży) i
**fault isolation** (wywołanie LLM na minuty nie blokuje CRUD-a). Kosztuje:
status jest eventually consistent, frontend musi pollować, a tekst pracy jedzie
przez wire i przez Redisa. Gdyby to była komercyjna apka dla jednego zespołu,
jeden serwis z Celery byłby prostszy i uczciwszy. Trzymamy dwa, bo worker skaluje
się osobno — i bo to jest ten projekt, na którym się tego uczysz.

### Ćwiczenie weryfikujące

Dwa terminale, jedna akcja z UI, prześledzić ją w obu logach naraz:

```bash
docker compose -f infra/docker-compose.yml logs -f app
```

```bash
docker compose -f infra/docker-compose.yml logs -f agent-worker
```

### Artefakt

Diagram sekwencji jednej akcji: klik → `app` → `agent` → Celery → graf → status
w Postgresie → polling → akceptacja. Do `docs/`.

### Pytania otwarte

- [ ] _(dopisuj tu swoje w trakcie sesji)_

---

# Blok B1 — agent: jak akcja przechodzi przez graf

**Sesje: 1**

### Ścieżka czytania

1. `agent/src/infrastructure/api/router.py` — przyjęcie żądania, walidacja typu akcji
2. `agent/src/application/tasks.py::run_action` — obwoluta: status, wytyczne, BYOK
3. `agent/src/application/graph.py::build_action_graph` — dispatcher po typie akcji
4. `agent/src/application/nodes/propose_topic.py` — najprostszy węzeł, wzorzec dla reszty
5. `agent/src/application/json_output.py` — jeden helper na wszystkie węzły
6. `agent/src/application/excerpt.py` — drugi taki helper: **decyduje, co model
   w ogóle widzi z pracy** (fragment + mapa całości + reguły, czego z tego
   fragmentu nie wolno wnioskować). Przechodzi przez niego każdy węzeł czytający
   tekst pracy
7. `agent/src/application/nodes/review.py` — **dopiero na końcu** (434 linie, jedyny czterowęzłowy)

### Trzy pojęcia, bez których reszta się nie klei

1. **`ActionState` to jeden schemat na sześć akcji** (`agent/src/application/state.py`).
   Wszystko specyficzne siedzi w worku `context: dict`. Nowa akcja = węzeł + prompt
   + builder kontekstu, a nie nowy stan, task i endpoint.
   *Koszt:* `context` jest nietypowany — kompilator nie powie ci, że węzeł czyta
   klucz, którego `app` nie wysyła. To wychodzi w runtime.
   *Żywy przykład w repo:* `document_map` — klucz pisany w `app`
   (`context.py::_document_map`), czytany w agencie (`excerpt.py`), bez żadnej
   kontroli typów między nimi. Warto przy tym bloku prześledzić, co się stanie,
   gdy go zabraknie: węzeł dostaje sam fragment i **nie ma jak odróżnić rozdziału
   nienapisanego od nieprzysłanego**. Dokładnie to produkowało recenzje
   wypisujące braki rozdziałów, które w pracy są.
2. **Węzły nigdy nie rzucają wyjątkiem.** Błąd ląduje w `state["error"]`, graf
   dobiega do końca, a `_run_graph` dopiero na końcu decyduje: `completed` czy
   `failed`. Odwrotność normalnego odruchu — powód: w czterowęzłowym review
   padnięcie węzła drugiego nie ma kasować pracy pierwszego.
3. **Status pisany po obu stronach grafu, do Postgresa**
   (`agent/src/infrastructure/task_status.py`). Wynik akcji nie może zależeć od
   TTL Redisa. To była świadoma naprawa w Fazie 2.

### Wątek poboczny: BYOK

`agent/src/infrastructure/llm_factory.py` — klucz siedzi w `ContextVar`, nie w
state, bo **state jest tym, co się serializuje** i co LangGraph checkpointowałby
do bazy. `use_credentials()` resetuje w `finally`, żeby prefork worker nie podał
klucza jednego promotora następnemu zadaniu. `model` dotyczy tylko Ollamy — to
tag lokalnego modelu, u dostawcy jedzie stały default.

### Ćwiczenie weryfikujące

Odpalić `propose_topic` i `generate_review` na tym samym studencie i porównać
w logach liczbę wywołań modelu (1 vs 4) oraz czas.

### Artefakt

Diagram grafu (sześć akcji, pięć jednowęzłowych + jedna czterowęzłowa) i notatka
„gdzie jest stan, a gdzie klucz".

### Pytania otwarte

- [ ] _(tu)_

---

# Blok B2 — pgvector: od pliku .md do promptu

**Sesje: 1**

### Ścieżka czytania (krótka, cała czytelna w jednej sesji)

1. `agent/src/application/guidelines.py::retrieve_relevant_guidelines` — orkiestracja + chunkowanie
2. `agent/src/infrastructure/embeddings.py::embed_query` — osobny `EMBEDDING_BASE_URL`
3. `agent/src/infrastructure/guideline_store.py::search_chunks` — własny engine (worker jest synchroniczny)
4. `agent/src/infrastructure/repositories.py::GuidelineChunkRepository.search` — **serce**: pinned + nearest
5. `agent/src/application/tasks.py::_with_guidelines` — kto to w ogóle woła i dla których akcji
6. `agent/scripts/ingest_guidelines.py` — druga strona: jak wektory tam trafiają

### Cztery rzeczy nieoczywiste, warte zatrzymania

1. **Chunkowanie idzie po nagłówkach dokumentu, nie po liczbie znaków** — to są
   numerowane reguły, a reguła przecięta w pół retrieveuje się jako bełkot i nie
   da się jej zacytować. Sekcje > 900 znaków dzielą się po `###`, każdy podrozdział
   niesie ze sobą nagłówek rodzica.
2. **Część sekcji jest przypięta na sztywno** (`_ALWAYS_INCLUDE`:
   severity/klasyfikacja/scoring). Bez tego model dostaje trzy sekcje o strukturze
   i zgaduje, co w tym dokumencie znaczy „critical".
3. **Kolumna `embedding` nie ma wymiaru** — przez co nie da się założyć HNSW, ale
   można trzymać wektory z dwóch modeli obok siebie i nigdy ich nie pomieszać
   (retrieval filtruje po `embedding_model`). Przy 14–18 chunkach skan sekwencyjny
   i tak wygrywa. Podręcznikowy trade-off: **elastyczność modelu ↔ indeksowalność**.
4. **Retrieval nigdy nie wywala akcji.** Brak ingestii, padnięty Ollama, blip bazy
   — wszystko kończy się całym plikiem wytycznych, czyli tym, co było przed Fazą 5.

### Ćwiczenia — tu bez klikania się tego nie zrozumie

Struktura tabeli i co w niej siedzi:

```bash
docker exec infra-postgres-1 psql -U user -d thesis_reviewer -c "\d analysis.guideline_chunks"
```

```bash
docker exec infra-postgres-1 psql -U user -d thesis_reviewer -c "select section, length(chunk_text) len, always_include from analysis.guideline_chunks where thesis_type='bachelor' order by section;"
```

Surowe dystanse — bierzemy jeden chunk jako zapytanie i rankujemy resztę.
Pokazuje, jak blisko siebie są sekcje tego samego dokumentu (i dlaczego przy
grubych chunkach retrieval zwracał 99% pliku):

```bash
docker exec infra-postgres-1 psql -U user -d thesis_reviewer -c "with q as (select embedding from analysis.guideline_chunks where thesis_type='bachelor' and section like '%Bibliography%' limit 1) select section, round((embedding <=> (select embedding from q))::numeric, 4) as dist from analysis.guideline_chunks where thesis_type='bachelor' order by dist;"
```

Re-ingestia (idempotentna — dwa uruchomienia zostawiają jedną kopię):

```bash
make ingest-guidelines
```

Na koniec **celowa awaria**, najbardziej pouczające ćwiczenie z całego bloku:
podmienić `EMBEDDING_BASE_URL` na nieistniejący host, odpalić `generate_review`
i sprawdzić, że akcja przechodzi normalnie, tylko z `guideline_embedding_failed`
w logu i całym plikiem w prompcie.

### Artefakt

Diagram „od pliku .md do promptu" + notatka: jakie sekcje retrieval wybrał dla
twojej testowej pracy (dziś 44–65% dokumentu, zależnie od zapytania).

### Pytania otwarte

- [ ] _(tu)_

---

# Blok C — deploy i CI/CD: jedna sesja i jedna decyzja

**Sesje: 1 (czytanie jest krótkie — decyzja jest długa)**

### Stan faktyczny w trzech zdaniach

- **GitHub Actions to brama jakości** — pięć jobów: `app`, `agent`, `frontend`,
  `migrations` (schemat od zera na `pgvector/pgvector:pg16`), `sonarqube`
  (pomijany bez tokenu, żeby fork nie świecił na czerwono).
- **Jenkins to deploy** — build na hoście → migracje trzech lineage → `up -d` →
  healthcheck przez `/health` w `app` (który raportuje też agenta). Produkcyjny
  `.env` z Jenkins credentials, kasowany w `post { always }`.
- **pre-commit to higiena** — ruff, eslint, `detect-private-key`. Świadomie bez
  pytest i pyright: hook, który trwa 55 s, jest hookiem wyłączanym przez `--no-verify`.

### Ścieżka czytania

1. `.github/workflows/ci.yml`
2. `infra/jenkins/Jenkinsfile`
3. `Makefile` (dev stack vs prod stack, hot reload przez override)
4. `infra/docker-compose.yml` + `infra/docker-compose.override.yml`

### Znany rozjazd w dokumentacji

CLAUDE.md §4 wymienia `.github/workflows/cd.yml` — **tego pliku nie ma**. Deploy
jest wyłącznie po stronie Jenkinsa. Do poprawienia przy okazji tego bloku.

### Decyzja do podjęcia: co „deploy" ma znaczyć dla tego projektu

| Opcja | Zyskujesz | Oddajesz |
|---|---|---|
| **Zostaje lokalnie** (compose na maszynie/NAS) | zero kosztu, Ollama 30B za darmo, pełna prywatność prac | nikt poza tobą tego nie użyje; „deploy" to nazwa na `docker compose up` |
| **VPS + reverse proxy + GHCR** | realny deploy, HTTPS, rollback po tagach obrazu, ktoś inny może wejść | VPS nie pociągnie 30B → akcje tylko na BYOK; koszt miesięczny |
| **Hybryda: apka na VPS, Ollama w domu przez Tailscale** | jedno i drugie — publiczny dostęp i lokalny model | najwięcej ruchomych części; twoje łącze staje się zależnością produkcyjną |

**Rekomendacja:** opcja 2, ale nie od razu w całości. Najpierw jeden klocek, wart
zachodu niezależnie od wyboru: **rejestr obrazów (GHCR)**. Dziś Jenkins buduje na
hoście docelowym, więc deploy = build, a rollback nie ma do czego wrócić poza
`git checkout`. To jedna zmiana w `ci.yml` i w Jenkinsfile'u — i dopiero ona
odblokowuje sensowną rozmowę o stagingu i rollbacku. Reverse proxy + HTTPS to
następny klocek, nie ten sam.

Hybryda jest edukacyjnie najciekawsza (i kusząca, skoro i tak masz NAS) — ale
jako trzeci krok, nie pierwszy.

### Artefakt

ADR `0006-deployment-target.md` z wybraną opcją i uzasadnieniem + GHCR jako
pierwsze zadanie implementacyjne.

### Pytania otwarte

- [ ] _(tu)_

---

# Blok D — front: redesign

**Sesje: 2–3 · robić PO blokach A i B**

Powód kolejności: dopiero wiedząc, że `mentoring.agent_actions` trzyma `input_ref`
z provenance, `accepted_at`, `output` jako JSONB i historię per `(student_id,
action_type)`, wiesz, co w ogóle masz do pokazania. Redesign zrobiony wcześniej
zaprojektuje ekrany do danych, których nie ma.

### Stan wyjściowy

Next 16 + React 19 + Tailwind 4 + `next-themes` + tabler icons, SWR do pollingu,
RHF + zod na formularzach — **bez żadnej biblioteki komponentów**. Dlatego wygląda
minimalnie: każdy przycisk jest pisany ręcznie w Tailwindzie i nikt nie miał czasu
na drugą iterację.

### Decyzja narzędziowa

| Podejście | Za | Przeciw |
|---|---|---|
| **Claude Design → potem kod** | tanio odrzucasz nietrafione układy przed dotknięciem Reacta; canvas, który sam klikasz | dodatkowy krok tłumaczenia design → React; ryzyko zaprojektowania ekranu do danych, których backend nie ma |
| **Prosto w kod + shadcn/ui** | zero straty w tłumaczeniu, od razu prawdziwe dane | iteracja nad układem w kodzie jest wolna i kończy się akceptacją pierwszej rzeczy, która się wyrenderowała |
| **Jedno i drugie** | decyzje wizualne tanio, implementacja na gotowym systemie komponentów | dwa kroki zamiast jednego |

**Rekomendacja: trzecie.** Claude Design na cztery ekrany — lista studentów, karta
studenta z akcjami, widok wyniku akcji, landing/login — potem implementacja na
**shadcn/ui** (Tailwind 4 i React 19 wspierane, wchodzi bez tarcia w to, co jest).

Claude Design zwraca się dokładnie tam, gdzie jest dziś problem: nie w tym, że
przyciski są brzydkie, tylko w tym, że **nikt nie zaprojektował hierarchii karty
studenta** — co jest najważniejsze, gdy patrzysz na studenta po miesiącu przerwy.

### Dług do domknięcia przy okazji (to ta sama robota)

- [x] **Historia wyników akcji** — zrobione 2026-09-12 (`15fc21d`): każda
      zakończona akcja rozwija się w miejscu i pokazuje zapisany wynik. Dane
      leżały w `mentoring.agent_actions.output` od początku — brakowało wyłącznie
      widoku. Warte obejrzenia jako przykład „dług UI, nie dług backendu".
- [ ] **`review_tone` w UI** — graf i prompty obsługują siedem tonów
      ([review-tone-spec.md](review-tone-spec.md)), UI zawsze wysyła `auto`.
- [ ] **Testy E2E (Playwright)** — do rozważenia, skoro i tak przepisujemy ekrany.

### Pytania otwarte

- [ ] _(tu)_

---

## Kolejność i status

| Blok | Sesje | Artefakt | Status |
|---|---|---|---|
| A — architektura | 1 | diagram sekwencji akcji | ☐ |
| B1 — graf i węzły | 1 | diagram grafu + notatka o stanie/BYOK | ☐ |
| B2 — pgvector | 1 | diagram ścieżki retrievalu + wyniki zapytań | ☐ |
| C — deploy/CI | 1 | ADR 0006 + GHCR jako pierwsze zadanie | ☐ |
| D — front | 2–3 | canvas → implementacja + historia akcji | ☐ |

---

## Ściągawka: komendy

```bash
make dev                  # cały stack z hot reloadem (source mounted, uvicorn --reload)
make ps                   # status kontenerów
make logs                 # logi ze wszystkiego
make migrate              # oba lineage `app` (identity + mentoring)
make ingest-guidelines    # embedding wytycznych do pgvectora
make shell-agent          # shell w kontenerze agenta
make front-dev            # Next dev server lokalnie (koliduje z kontenerem na :3000)
```

Testy:

```bash
cd app && uv run pytest -q
```

```bash
cd agent && uv run pytest -q
```

```bash
cd frontend && npx vitest run
```

Baza (user `user`, db `thesis_reviewer`, kontener `infra-postgres-1`):

```bash
docker exec -it infra-postgres-1 psql -U user -d thesis_reviewer
```

## Ściągawka: endpointy

**`app` :8000 — identity**
`POST /auth/login` · `POST /auth/refresh` · `POST /auth/logout` ·
`POST|GET /users` · `GET /users/me` · `DELETE /users/{id}` ·
`PATCH /users/me/password` · `PATCH|DELETE /settings/api-key` ·
`GET /settings/api-key/status` · `GET /admin/login-events`

**`app` :8000 — mentoring** (prefix `/students`)
`POST|GET /students` · `GET|PATCH /students/{id}` ·
`POST|GET /students/{id}/meeting-notes` ·
`POST|GET /students/{id}/drafts` ·
`POST|GET /students/{id}/actions` · `GET /students/{id}/actions/{action_id}` ·
`PATCH /students/{id}/actions/{action_id}/accept`

**`agent` :8002**
`POST /actions` (202) · `GET /actions/{task_id}` · `GET /health`

## Ściągawka: nazwy eventów w logach

Przydatne do `grep`owania podczas tracowania:

| Event | Gdzie | Znaczy |
|---|---|---|
| `run_action.started` / `.completed` / `.failed` | worker | cykl życia zadania (`byok_provider` widoczne, klucz nigdy) |
| `guidelines_retrieved` | worker | **które sekcje** wytycznych trafiły do promptu |
| `guideline_embedding_failed` | worker | embedding padł → fallback do całego pliku |
| `guidelines_not_ingested_using_file` | worker | nic nie zaingestowane dla tego typu/modelu |
| `guideline_search_failed` | worker | baza nie odpowiedziała na retrieval |
| `task_status_write_failed` | worker | **cichy** — status w bazie został nieświeży |
| `token_store_check_failed_fail_open` | app | Redis padł, odwołane tokeny są akceptowane |

---

*Ostatnia aktualizacja: 2026-09-13 — stan wyjściowy przeliczony na nowo,
`excerpt.py` i `outline.py` dopisane do ścieżek czytania, historia akcji
odhaczona w Bloku D.*
