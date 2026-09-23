# Technical Debt & Known Issues

> Plik zbiera rzeczy do naprawy, które zostały świadomie odłożone.  
> Aktualizuj go przy każdej sesji — dodawaj nowe rzeczy, wykreślaj naprawione.

---

## Jakość kodu — stan faktyczny (zweryfikowany 2026-09-05)

- [ ] **Martwa ścieżka „widzi wszystkich studentów”** (od ADR 0008, 2026-09-23) —
  żadna rola nie ma już `VIEW_ALL_STUDENTS`, więc `Caller.can_view_all` i gałęzie
  „view all” w `mentoring/infrastructure/repositories.py` (oraz nieużywane
  `VIEW_ALL_ANALYSES`) są nieosiągalne. Usunąć albo świadomie zostawić pod
  przyszłą rolę nadzoru (np. dziekanat).

- [~] **`pyright --strict` — kod produkcyjny czysty, testy nie.** Historycznie nie
  przechodził nigdy (przed konsolidacją: `identity` **736** błędów, `parser` **88**;
  po konsolidacji `app` **160**). Od Fazy 6 **`pyright src` zwraca 0 błędów w obu
  serwisach** i pilnuje tego CI. Zostaje ok. **250 błędów w `tests/**`** — prawie
  wyłącznie `reportUnknownMemberType` na `TestClient`/`httpx`.
  Naprawka: anotować odpowiedzi w testach albo per-file suppression dla `tests/**`
  — świadomie, jako osobna zmiana.

- [ ] **`ruff format` nie jest włączony** — przeformatowałby ~30 istniejących plików
  w obu serwisach. Warto to zrobić, ale jako osobną zmianę, nie przy okazji CI
  (ten sam powód co przy pinach `fastapi`/`starlette`). Wtedy dołożyć hook
  `ruff-format` do `.pre-commit-config.yaml` i krok do CI.

- [x] ~~**`ruff` w `agent/` — 36 błędów**~~ — naprawione w Fazie 2 (2026-09-05).
  Oba serwisy są czyste. Pliki z promptami (`agent/src/application/prompts/*.py`,
  `nodes/review.py`) mają świadomy per-file wyjątek na `E501` — łamanie linii w
  literale zmienia prompt, nie formatowanie.

- [ ] **Piny `fastapi==0.136.3` + `starlette==1.2.1` w `app/pyproject.toml`** — świeży
  lockfile podbijał je do 0.141 / 1.6, co wciągnęłoby nietestowany upgrade zależności
  w środek refaktoru strukturalnego. Odpiąć i zaktualizować osobno (starlette 1.6
  deprecjonuje też `httpx` w `TestClient`).

- [ ] **Coverage nie mierzy ciał async endpointów wykonywanych przez `TestClient`** —
  np. `/auth/login` w `identity/infrastructure/router.py` pokazuje się jako niepokryte
  mimo kilkudziesięciu wywołań w testach (kod leci w wątku roboczym portalu anyio).
  Skutek praktyczny: pokrycie warstwy application trzeba robić testami bezpośrednimi,
  a liczby dla routerów są zaniżone. Do zdiagnozowania osobno (prawdopodobnie
  `COVERAGE_CORE=sysmon` / tracing wątków).

- [ ] **SQLite w testach gubi `tzinfo`** — `DateTime(timezone=True)` odczytany po
  `refresh()` wraca naiwny, na Postgresie zostaje aware. Jedno miejsce już to
  obchodzi (`tests/test_mentoring/test_student_service.py`). Przy Fazie 2 dochodzą
  kolejne znaczniki czasu (`accepted_at`, `updated_at`) — albo znormalizować odczyt
  w repozytoriach, albo testować czas na Postgresie.

- [ ] **Zapis statusu z workera połyka błędy bazy** — `agent/src/infrastructure/task_status.py`
  loguje i idzie dalej, żeby awaria zapisu nie powodowała retry analizy, która się udała
  (kilka minut pracy LLM). Skutek: przy niedostępnej bazie wiersz zostaje nieświeży, a
  jedynym śladem jest log `task_status_write_failed`. Wymaga alertu na ten event, tak samo
  jak `token_store_check_failed_fail_open`.

- [ ] **Zawieszony worker zostawia akcję w `running` na zawsze** — status jest zapisywany
  przed i po wywołaniu grafu; jeśli proces zginie w środku (OOM, kill), nic tego nie
  posprząta. Naprawka: timeout na akcję (`updated_at` starsze niż N minut → `failed`)
  albo Celery `task_reject_on_worker_lost` + sprzątanie przy starcie.

---

## Pozostałości po konsolidacji — ✅ usunięte w Fazie 3 (2026-09-06)

- [x] ~~`app/src/proxy/`~~ — proxy `/analysis/*` usunięte; `/health` przeniesiony do
  `app/src/shared/health.py`.
- [x] ~~`app/src/document/router.py` (`POST /extract`)~~ — ekstrakcja wołana in-process
  przez `POST /students/{id}/drafts`.
- [x] ~~`GATEWAY_URL` + `PARSER_URL` we frontendzie~~ — jedno `APP_URL`.
- [x] ~~Frontend nie wie nic o studentach~~ — `/students` i `/students/[id]` z akcjami,
  wersjami pracy i notatkami.
- [x] ~~`agent_tasks.evaluation_id` i task `analyze_thesis`~~ — usunięte razem z
  `POST /analysis` (migracja `0003_drop_legacy`).

---

## Gateway (historyczne — serwis usunięty w Fazie 0, dług przeniesiony do `app`)

### Bezpieczeństwo

- [ ] **Brak revokacji access tokenów** — po wylogowaniu access token (15 min) pozostaje ważny do naturalnego wygaśnięcia. Naprawka: Redis JTI blacklist analogiczna do `RefreshTokenStore`, sprawdzana w `get_current_user`.

- [ ] **Fail-open w `RefreshTokenStore`** — jeśli Redis jest niedostępny, `is_revoked()` zwraca `False` (odwołane tokeny są akceptowane). Celowy kompromis dostępność vs. bezpieczeństwo — wymaga alertu/monitoringu na log event `token_store_check_failed_fail_open`.

### Funkcjonalność

- [ ] **Brak password reset flow** — użytkownik nie może odzyskać zapomnianego hasła. Wymaga integracji SMTP i tokenu jednorazowego (np. krótkotrwały JWT wysyłany na e-mail).

- [ ] **Brak weryfikacji czy worker Celery działa** — zadanie trafia do kolejki cicho; jeśli
  worker nie chodzi, akcja zostaje w statusie `pending` w nieskończoność. Faza 2 załatwiła
  część problemu (padnięcie brokera przy wysyłce daje teraz `failed` + 503), ale martwy
  worker nadal jest niewidoczny. Naprawka: endpoint `GET /health/worker` sprawdzający
  `celery_app.control.inspect().ping()`.

- [ ] **Brak soft delete użytkowników** — `DELETE /users/{id}` usuwa rekord na twardo. Rozważyć pole `deleted_at` i filtrowanie w zapytaniach.

### Obserwability

- [ ] **Brak metryk Prometheus / OpenTelemetry** — nie ma wglądu w liczbę requestów, błędów, czas odpowiedzi. Rozważyć `prometheus-fastapi-instrumentator` lub OTEL SDK.

- [ ] **Brak access logu HTTP** — logi są w logice biznesowej, ale żaden middleware nie zapisuje każdego żądania (metoda, ścieżka, status, czas). Naprawka: middleware `structlog` na poziomie ASGI.

### Drobne

- [x] ~~**Email validation regex zbyt prosta**~~ — naprawione: `UserRegistration` używa
  biblioteki `email-validator` (commit `097798c`).

- [ ] **Brak rate limitingu na polling akcji** — `GET /students/{id}/actions/{action_id}`
  odpytuje `agent` przy każdym wywołaniu, dopóki akcja nie jest terminalna. Frontend pyta
  co 3 s; nic nie broni się przed szybszym klientem.

---

## BYOK (Faza 4)

- [ ] **Klucz przechodzi przez brokera Redis w jawnej postaci** — jest argumentem
  zadania Celery, więc leży w kolejce do momentu odebrania przez workera. Celery nie
  zapisuje argumentów w result backendzie (`result_extended` wyłączone), więc ekspozycja
  jest ulotna i wewnątrz sieci compose. Docelowo: przekazywać referencję zamiast klucza
  i pozwolić workerowi odszyfrować go samodzielnie.

- [ ] **Nie można wybrać modelu u dostawcy** — BYOK używa stałych domyślnych
  (`claude-sonnet-4-20250514`, `gpt-4o`); parametr `model` dotyczy tylko Ollamy, bo to
  tag lokalnego modelu. Do wystawienia razem z listą modeli per dostawca.

- [ ] **Brak walidacji klucza przy zapisie** — zapisujemy, co przyszło; użytkownik
  dowiaduje się o błędnym kluczu dopiero z nieudanej akcji (401 od dostawcy). Naprawka:
  lekki „ping" do dostawcy przy `PATCH /settings/api-key`.

- [ ] **Brak śladu kosztów** — nie zapisujemy, ile tokenów zużyła akcja ani na czyim
  koncie. Przy BYOK to informacja, którą promotor chciałby widzieć.

---

## RAG nad wytycznymi (Faza 5)

- [x] ~~**Model embeddingów nie jest jeszcze uruchomiony**~~ — `nomic-embed-text`
  pobrany do kontenera `ollama` (2026-09-06), wytyczne zaingestowane (14 + 18 chunków,
  768 wymiarów), retrieval działa na żywo. Serwer czatu tego użytkownika nie obsługuje
  embeddingów, dlatego doszło osobne `EMBEDDING_BASE_URL`.

- [ ] **Krótkie podsekcje szumią w wynikach** — chunki po 50-60 znaków (np. „1.1 Strona
  tytułowa") potrafią trafić do top-k przy zapytaniu, z którym nie mają wiele wspólnego.
  Do rozważenia: łączenie sąsiednich krótkich podsekcji albo próg minimalnej długości.

- [ ] **Brak indeksu ANN** — kolumna `embedding` jest bezwymiarowa, więc nie da się na
  niej założyć HNSW/IVFFlat. Przy kilkunastu chunkach na typ pracy skan sekwencyjny jest
  szybszy i dokładniejszy; przy większym korpusie trzeba ustalić wymiar i dołożyć indeks.

- [ ] **Zapytanie to pierwsze 2000 znaków pracy** — przybliżenie: nasz „query" to
  początek dokumentu (temat, problem, metoda). Lepsze byłoby zapytanie per sekcja
  wymogów albo streszczenie pracy.

- [ ] **Ingestia nie jest wersjonowana** — zmiana pliku wymogów wymaga ręcznego
  `make ingest-guidelines`; nic nie wykrywa, że wektory są starsze niż plik.

---

## Agent / Frontend

- [ ] **`agent-worker` zawsze raportuje `unhealthy`** — dziedziczy HEALTHCHECK z obrazu
  agenta, który sprawdza HTTP na :8002, a worker nie wystawia HTTP. Kosmetyka, ale myli
  przy `docker compose ps`. Naprawka: własny healthcheck (`celery inspect ping`) albo
  `healthcheck: disable: true` w compose.

- [ ] **Brak testów E2E frontendu** — komponenty mają testy jednostkowe (vitest), ale nikt
  nie klika przez ścieżkę „dodaj studenta → wgraj pracę → uruchom akcję → zaakceptuj".
  Do rozważenia Playwright przy Fazie 6.

- [ ] **Frontend nie pokazuje historii wyników akcji** — lista akcji na stronie studenta
  pokazuje typ i status, ale kliknięcie w zakończoną akcję nie otwiera jej wyniku;
  wynik widać tylko dla akcji uruchomionej w bieżącej sesji.

- [ ] **`review_tone` niedostępny w akcjach mentoringowych** — `generate_review` jest
  zawsze uruchamiany z tonem `auto`, mimo że graf i prompty obsługują siedem tonów
  (spec: `docs/specs/review-tone-spec.md`). Do wystawienia w UI.

---

## CI/CD (Faza 6)

- [ ] **Brak rejestru obrazów** — Jenkins buduje obrazy na hoście docelowym zamiast
  ciągnąć je z GHCR. Świadomie odłożone (plan zostawiał wybór otwarty), ale to znaczy,
  że deploy = build, a rollback nie ma do czego wrócić poza `git checkout`.

- [ ] **Brak deploymentu innego niż lokalny compose** — nie ma środowiska staging,
  nie ma HTTPS/reverse proxy, `ENVIRONMENT=production` wpływa tylko na flagę
  `Secure` w ciasteczkach.

- [ ] **SonarQube nieskonfigurowany** — `sonar-project.properties` istnieje, ale nikt
  nie postawił serwera ani nie ustawił `SONAR_TOKEN`; job w CI się pomija.

- [ ] **Brak testów E2E w CI** — pipeline sprawdza jednostki i migracje, nikt nie
  uruchamia prawdziwej akcji przez `docker compose` (wymagałoby modelu w runnerze).

---

## Infrastruktura

- [ ] **Brak healthchecku Celery workera w `docker-compose`** — kontener `agent` startuje, ale `docker-compose` nie wie czy worker faktycznie obsługuje zadania.

- [ ] **Dependabot / Renovate Bot nie skonfigurowany** — zależności nie są automatycznie aktualizowane (faza 5 z CLAUDE.md).

---

*Ostatnia aktualizacja: 2026-09-05 (po Fazie 0 — konsolidacja serwisów)*
