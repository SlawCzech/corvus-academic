# Technical Debt & Known Issues

> Plik zbiera rzeczy do naprawy, które zostały świadomie odłożone.  
> Aktualizuj go przy każdej sesji — dodawaj nowe rzeczy, wykreślaj naprawione.

---

## Przegląd bezpieczeństwa przed deployem (2026-10-09)

Naprawione od razu: podatne zależności (Next.js — krytyczna, PyJWT, Starlette,
urllib3), klucz BYOK widoczny w Flowerze i logach workera (`kwargsrepr`), limit
logowań wspólny dla całego świata (brak `X-Forwarded-For`), otwarte
przekierowanie w `/api/auth/refresh`, Node 20 po EOL, `.dockerignore`, przez
który obraz frontendu w ogóle się nie budował, Redis zapisujący wiadomości
tasków (z kluczem) na dysk. Sekretów w repo ani w historii gita nie ma.

Zostaje:

- [ ] **Odświeżanie sesji nie działa.** `app` ustawia refresh token jako cookie
  na odpowiedzi do serwera Next.js (który je wyrzuca), a frontend czeka na
  `refresh_token` w treści odpowiedzi — więc nigdy go nie dostaje. Sesja trwa tyle,
  co access token (12 h), potem logowanie od nowa. Przy okazji: access token nie
  jest sprawdzany w bazie, więc usunięty użytkownik i wylogowanie nie odcinają
  ważnego tokenu przed upływem 12 h.
- [ ] **Niepoprawny e-mail przy `POST /users` → 500, nie 422.** `ValueError`
  z `UserRegistration` nie jest mapowany w `users_router.py` (np. adres w domenie
  zarezerwowanej, jak `.local`).
- [ ] **Brak Content-Security-Policy.** Caddy wysyła HSTS, `nosniff`,
  `X-Frame-Options`, `Referrer-Policy`; CSP wymaga noncy dla skryptów inline
  Next.js — osobna praca.
- [ ] **`middleware.ts` → `proxy.ts`.** Next 16 zgłasza konwencję `middleware`
  jako przestarzałą.
- [ ] **Hydration mismatch ikony motywu** w `Sidebar` (słońce/księżyc zależne od
  motywu po stronie klienta).
- [ ] **`@testing-library/*` w `dependencies`** zamiast `devDependencies` —
  `npm audit --omit=dev` pokazuje przez to vitest jako zależność produkcyjną.
- [ ] **Parsowanie niezaufanych PDF/DOCX** w procesie `app` (limit rozmiaru jest,
  limitu czasu i pamięci ekstrakcji nie ma). Przy kilku zaufanych testerach do
  przyjęcia; przy otwartej rejestracji — do osobnego procesu z limitami.

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

- [x] ~~**Zawieszony worker zostawia akcję w `running` na zawsze**~~ — od 2026-09-30
  (ADR 0010) taski są potwierdzane po zakończeniu, a padnięty worker wznawia
  przebieg z checkpointu. Zostaje brak limitu ponownych dostarczeń dla taska,
  który za każdym razem zabija workera. Pierwotny opis: status jest zapisywany
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

- [x] ~~**Brak revokacji access tokenów**~~ — od 2026-10-03 access token ma `jti`,
  `/auth/logout` wpisuje go na listę w Redis na resztę jego ważności, a
  `get_current_user` ją sprawdza. Route `/api/auth/logout` we froncie wysyła teraz
  token w `Authorization` — wcześniej wysyłał tylko refresh token, i to w JSON-ie,
  którego backend nie czyta. Tokeny wydane przed tą zmianą (bez `jti`) są odrzucane:
  jednorazowe ponowne logowanie.

- [ ] **Refresh z UI nie działa** (znalezione 2026-10-03) — `app` oddaje refresh token
  w `Set-Cookie` na ścieżce `/auth/refresh`, a route `/api/auth/login` we froncie
  szuka go w JSON-ie (`data.refresh_token`), więc Next nigdy nie zapisuje ciasteczka
  `refresh_token`, a `/api/auth/refresh` wysyła go w treści, której backend nie czyta.
  Sesję w praktyce trzyma sam access token (12 h). Naprawka: przepisać `Set-Cookie` z
  odpowiedzi logowania na ciasteczko Next i wysyłać je do `app` w nagłówku `Cookie`
  (tak jak robi to już `/api/auth/logout`); dopiero wtedy da się skrócić access token.

- [ ] **Fail-open w `RevokedTokenStore`** — jeśli Redis jest niedostępny, `is_revoked()` zwraca `False` (odwołane tokeny, od 2026-10-03 także access tokeny, są akceptowane). Celowy kompromis dostępność vs. bezpieczeństwo — wymaga alertu/monitoringu na log event `token_store_check_failed_fail_open`.

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

- [x] ~~**Klucz przechodzi przez brokera Redis w jawnej postaci**~~ — od 2026-10-03
  API agenta szyfruje klucz Fernetem (klucz wyprowadzony HKDF z `JWT_SECRET`), worker
  odszyfrowuje go dopiero w tasku — [ADR 0012](adr/0012-seal-the-provider-key-for-the-task-queue.md).
  Ekspozycja nie była „ulotna”: przy `acks_late` (ADR 0010) wiadomość leży w Redis przez
  cały przebieg, a Flower pokazuje argumenty. Referencja zamiast klucza odrzucona —
  dałaby workerowi `FERNET_KEY` do wszystkich zapisanych kluczy. Zostaje: skok
  `app` → `agent` to jawny HTTP w sieci compose (TLS między serwisami, przy deployu).

- [ ] **Nie można wybrać modelu u dostawcy** — BYOK używa stałych domyślnych
  (`claude-sonnet-5-5`, `gpt-6.1-sol`); parametr `model` dotyczy tylko Ollamy, bo to
  tag lokalnego modelu. Do wystawienia razem z listą modeli per dostawca.

- [x] ~~**Brak walidacji klucza przy zapisie**~~ — `PATCH /settings/api-key` pyta
  dostawcę o listę modeli; odrzucony klucz to 422 i nie jest zapisywany (2026-09-30).
  Sprawdza sam klucz, nie saldo — brak środków wychodzi przy akcji, z kodem
  `provider_no_credits`.

- [x] ~~**Brak śladu kosztów**~~ — od 2026-10-03 każda akcja ma `usage`: tokeny
  wejścia i wyjścia, razem i per model, tak jak je raportuje dostawca (callback
  `UsageMeter` na przebiegu grafu, `agent/src/infrastructure/usage.py`). Agent
  dodaje do `analysis.agent_tasks.usage` po każdym przebiegu (wznowienie po pauzie
  i retry się sumują), `app` kopiuje do `mentoring.agent_actions.usage`, UI pokazuje
  pod wynikiem. Zostaje: **tokeny, nie złotówki** — cennik dostawcy zmienia się
  częściej niż kod; przeliczenie można dołożyć w UI. Przebieg zabity w połowie
  (OOM, kill) gubi swój licznik — liczy się dopiero na końcu przebiegu.

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

- [x] ~~**`agent-worker` zawsze raportuje `unhealthy`**~~ — naprawione 2026-09-12
  (`celery inspect ping` jako healthcheck). Pierwotny opis: dziedziczy HEALTHCHECK z obrazu
  agenta, który sprawdza HTTP na :8002, a worker nie wystawia HTTP. Kosmetyka, ale myli
  przy `docker compose ps`. Naprawka: własny healthcheck (`celery inspect ping`) albo
  `healthcheck: disable: true` w compose.

- [ ] **Brak testów E2E frontendu** — komponenty mają testy jednostkowe (vitest), ale nikt
  nie klika przez ścieżkę „dodaj studenta → wgraj pracę → uruchom akcję → zaakceptuj".
  Do rozważenia Playwright przy Fazie 6.

- [x] ~~**Frontend nie pokazuje historii wyników akcji**~~ — naprawione 2026-09-12;
  od 2026-10-01 niedokończona akcja w historii prowadzi do widoku postępu.
  Pierwotny opis: lista akcji na stronie studenta
  pokazuje typ i status, ale kliknięcie w zakończoną akcję nie otwiera jej wyniku;
  wynik widać tylko dla akcji uruchomionej w bieżącej sesji.

- [x] ~~**`review_tone` niedostępny w akcjach mentoringowych**~~ — wystawiony w UI
  2026-09-13/23. Pierwotny opis: `generate_review` jest
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

- [ ] **SonarQube nieskonfigurowany w CI** — kontener `sonarqube` chodzi lokalnie, ale
  nikt nie ustawił `SONAR_TOKEN`; job w CI się pomija.

- [ ] **Brak testów E2E w CI** — pipeline sprawdza jednostki i migracje, nikt nie
  uruchamia prawdziwej akcji przez `docker compose` (wymagałoby modelu w runnerze).

---

## Infrastruktura

- [x] ~~**Brak healthchecku Celery workera w `docker-compose`**~~ — jest od 2026-09-12.
  Pierwotny opis: kontener `agent` startuje, ale `docker-compose` nie wie czy worker faktycznie obsługuje zadania.

- [ ] **Dependabot / Renovate Bot nie skonfigurowany** — zależności nie są automatycznie aktualizowane (faza 5 z CLAUDE.md).

---

## Moduł AI na dostawcy (2026-10-01)

Pierwszy dzień akcji na żywo na Claude (`claude-sonnet-5-5`). Co zostało świadomie
odłożone:

- [x] ~~**OpenAI niesprawdzone**~~ — sprawdzone 2026-10-01: `propose_topic` na
  `gpt-6.1-sol` przez `ChatOpenAI`, 34 s ([demo-notes](demo-notes.md)). Zostaje: na
  OpenAI nie ma kalibracji ani evals — Claude jest głównym dostawcą (decyzja 2026-10-02).

- [x] ~~**Evals nie mają przebiegu na dostawcy**~~ — przebiegi na `claude-sonnet-5-5`
  (effort `medium`, sędzia ten sam model) od 2026-10-01, liczby w
  [specs/ai-extensions.md](specs/ai-extensions.md). Effort `medium` został; podział
  modeli per węzeł odpuszczony (decyzja 2026-10-02, [demo-notes](demo-notes.md)).

- [ ] **Brak przełączenia po odmowie klasyfikatora** — Sonnet 5.5 może odmówić
  (`stop_reason: refusal`); zgłaszamy to wprost, ale nie ponawiamy na innym modelu.
  Wymaga parametru beta, którego przez LangChain nie przetestowano.

- [ ] **Wymuszanie schematu tylko na Ollamie** — na dostawcy zostaje prompt, walidacja
  i jedna tura naprawcza. W recenzjach z 2026-10-01 dwie z trzech analiz potrzebowały
  tury naprawczej (brak `severity`); prompty podają teraz kształt JSON-a dosłownie,
  skutek niezmierzony. Docelowo: structured outputs dostawcy.

- [ ] **Uwagi w recenzji nie mają pozycji w dokumencie** — `section` to wolny tekst
  modelu, więc listy uwag nie da się posortować kolejnością rozdziałów (jest po wadze).

- [ ] **`check_progress` nie zna notatek ze spotkań** — porównuje dwie wersje, ale nie
  wie, o co promotor prosił między nimi.

- [ ] **Trzy ostatnie notatki, niezależnie od modelu** — `propose_topic` i
  `draft_meeting_note` dostają `_MAX_NOTES = 3`; na dostawcy mogłyby dostać wszystkie.

- [ ] **Katalogi biblioteczne: limity przyjęte, nie zmierzone** — Biblioteka Narodowa
  i Open Library nie podają limitów w nagłówkach; odstępy (0,2 s i 1 s) są ostrożnym
  założeniem. Crossref bez `CROSSREF_MAILTO` to 1 zapytanie/s — 45 s na 42 pozycje.

- [ ] **Lista „w toku” na dashboardzie odpytuje agenta przy każdym wejściu** — każda
  niedokończona akcja to jedno żądanie do agenta, sekwencyjnie.

---

*Ostatnia aktualizacja: 2026-10-01 (pierwsze akcje na dostawcy; katalogi biblioteczne;
pełny tekst dla modeli hostowanych)*
