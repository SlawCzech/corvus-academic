# Technical Debt & Known Issues

> Plik zbiera rzeczy do naprawy, które zostały świadomie odłożone.  
> Aktualizuj go przy każdej sesji — dodawaj nowe rzeczy, wykreślaj naprawione.

---

## Jakość kodu — stan faktyczny (zweryfikowany 2026-09-05)

- [ ] **`pyright --strict` NIE przechodzi i nigdy nie przechodził** — wbrew temu, co
  deklaruje `docs/sessions.md` ("ruff and pyright clean" przy sesjach 1.x–5.1).
  Zmierzone na kodzie sprzed konsolidacji (git worktree na HEAD): `identity` **736
  błędów**, `parser` **88**. Po konsolidacji `app` miał **160** (spadek wynika z usunięcia
  duplikatów i martwego kodu, nie z naprawy), po Fazie 1 ma **264**. Prawie wszystkie to
  `reportUnknownMemberType` na `TestClient`/`httpx` w testach — same **97** z nowych
  104 siedzi w `tests/test_mentoring/test_router.py`; `src/mentoring/` jest czyste
  (0 błędów w trybie strict).
  Naprawka: albo anotować odpowiedzi w testach, albo per-file suppression dla `tests/**`
  — ale świadomie, jako osobna zmiana, nie przy okazji refaktoru.

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

## Pozostałości po konsolidacji (Faza 0 → do usunięcia w Fazie 3)

- [ ] **`app/src/proxy/`** — przejściowe proxy `/analysis/*` → `agent`, żeby istniejący
  flow frontendu nie padł zanim powstaną endpointy mentoringowe. Znika razem z
  `/students/{id}/actions`.

- [ ] **`app/src/document/router.py` (`POST /extract`)** — z tego samego powodu.
  Docelowo ekstrakcja jest wołana in-process przez upload draftu, bez endpointu HTTP.

- [ ] **Frontend nadal czyta `GATEWAY_URL` i `PARSER_URL`** — oba wskazują teraz na
  `app:8000`. Zwinąć do jednego `APP_URL` przy przepisywaniu route handlerów.

- [ ] **Frontend nie wie nic o studentach ani akcjach AI** — cały interfejs mentoringu
  (roster, notatki, `propose_topic`) istnieje wyłącznie w API. `useAnalysis` uogólnia się
  na `useAction`, bo kontrakt 202-then-poll jest ten sam. Do zrobienia razem z Fazą 3.

- [ ] **`agent_tasks.evaluation_id` i task `analyze_thesis`** — pozostałość kontraktu
  sprzed mentoringu. Znikają razem z `POST /analysis` w Fazie 3.

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

- [ ] **Brak rate limitingu na `GET /analysis`** — polling statusu zadania nie jest ograniczony. Może być nadużywany przez frontend przy agresywnym pollingu.

---

## Agent / Parser / Frontend

> Serwisy w trakcie implementacji — dług będzie uzupełniany w miarę postępu.

---

## Infrastruktura

- [ ] **Brak healthchecku Celery workera w `docker-compose`** — kontener `agent` startuje, ale `docker-compose` nie wie czy worker faktycznie obsługuje zadania.

- [ ] **Dependabot / Renovate Bot nie skonfigurowany** — zależności nie są automatycznie aktualizowane (faza 5 z CLAUDE.md).

---

*Ostatnia aktualizacja: 2026-09-05 (po Fazie 0 — konsolidacja serwisów)*
