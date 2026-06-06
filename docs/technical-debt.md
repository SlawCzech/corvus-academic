# Technical Debt & Known Issues

> Plik zbiera rzeczy do naprawy, które zostały świadomie odłożone.  
> Aktualizuj go przy każdej sesji — dodawaj nowe rzeczy, wykreślaj naprawione.

---

## Gateway

### Bezpieczeństwo

- [ ] **Brak revokacji access tokenów** — po wylogowaniu access token (15 min) pozostaje ważny do naturalnego wygaśnięcia. Naprawka: Redis JTI blacklist analogiczna do `RefreshTokenStore`, sprawdzana w `get_current_user`.

- [ ] **Fail-open w `RefreshTokenStore`** — jeśli Redis jest niedostępny, `is_revoked()` zwraca `False` (odwołane tokeny są akceptowane). Celowy kompromis dostępność vs. bezpieczeństwo — wymaga alertu/monitoringu na log event `token_store_check_failed_fail_open`.

### Funkcjonalność

- [ ] **Brak password reset flow** — użytkownik nie może odzyskać zapomnianego hasła. Wymaga integracji SMTP i tokenu jednorazowego (np. krótkotrwały JWT wysyłany na e-mail).

- [ ] **Brak weryfikacji czy worker Celery działa** — zadanie trafia do kolejki cicho; jeśli worker nie chodzi, status analizy pozostaje `"analyzing"` w nieskończoność. Naprawka: endpoint `GET /health/worker` sprawdzający `celery_app.control.inspect().ping()`.

- [ ] **Brak soft delete użytkowników** — `DELETE /users/{id}` usuwa rekord na twardo. Rozważyć pole `deleted_at` i filtrowanie w zapytaniach.

### Obserwability

- [ ] **Brak metryk Prometheus / OpenTelemetry** — nie ma wglądu w liczbę requestów, błędów, czas odpowiedzi. Rozważyć `prometheus-fastapi-instrumentator` lub OTEL SDK.

- [ ] **Brak access logu HTTP** — logi są w logice biznesowej, ale żaden middleware nie zapisuje każdego żądania (metoda, ścieżka, status, czas). Naprawka: middleware `structlog` na poziomie ASGI.

### Drobne

- [ ] **Email validation regex zbyt prosta** — `^[^@\s]+@[^@\s]+\.[^@\s]+$` w `domain/user.py` odrzuca niektóre poprawne RFC 5321 adresy. Rozważyć `email-validator` (biblioteka) lub bardziej precyzyjny regex.

- [ ] **Brak rate limitingu na `GET /analysis`** — polling statusu zadania nie jest ograniczony. Może być nadużywany przez frontend przy agresywnym pollingu.

---

## Agent / Parser / Frontend

> Serwisy w trakcie implementacji — dług będzie uzupełniany w miarę postępu.

---

## Infrastruktura

- [ ] **Brak healthchecku Celery workera w `docker-compose`** — kontener `agent` startuje, ale `docker-compose` nie wie czy worker faktycznie obsługuje zadania.

- [ ] **Dependabot / Renovate Bot nie skonfigurowany** — zależności nie są automatycznie aktualizowane (faza 5 z CLAUDE.md).

---

*Ostatnia aktualizacja: 2026-06-06*
