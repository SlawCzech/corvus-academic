# Plan: zarządzanie użytkownikami i historia analiz

## Kontekst

Aktualny stan:
- `UserModel` i `AnalysisModel` w ORM już istnieją z kolumną `user_id` jako FK
- `UserRepository` ma `save`, `find_by_id`, `find_by_email`, `update_api_key`
- `AnalysisRepository` ma tylko `save` i `find_by_id` — brak scopingu do usera
- Login oparty o hardkodowany `user_store.py` (in-memory), nie bazę danych
- Brak rejestracji, brak historii analiz, brak CRUD użytkowników

---

## Warstwa domain (`gateway/src/domain/`)

### 1. Rozszerzyć encję `User`

Dodać pola potrzebne do CRUD i rejestracji:

```python
@dataclass(frozen=True)
class User:
    id: UUID
    email: str
    role: Role
    created_at: datetime        # ← nowe
```

### 2. Dodać value object `UserRegistration`

Reprezentuje dane wejściowe rejestracji — czysta walidacja bez ORM.
Hashowanie bcryptem odbywa się w **infrastructure** przed stworzeniem tego obiektu — do domeny trafia wyłącznie hash:

```python
@dataclass(frozen=True)
class UserRegistration:
    email: str
    hashed_password: str   # bcrypt hash — plaintext nigdy nie wychodzi z infra
    role: Role = Role.PROMOTOR
```

### 3. Dodać regułę domenową: unikalność emaila

Reguła należy do domeny, nie do infrastruktury:

```python
# domain/user.py
def validate_email(email: str) -> None:
    """Raises ValueError if email format is invalid."""
    ...
```

---

## Warstwa application (`gateway/src/application/`)

### 4. Use case: `UserService`

Nowy plik `application/user_service.py` — orkiestruje domain i repozytorium:

```python
class UserService:
    async def register(self, registration: UserRegistration) -> User: ...
    async def authenticate(self, email: str, password: str) -> User | None: ...
    async def get_by_id(self, user_id: UUID) -> User | None: ...
    async def list_all(self) -> list[User]: ...          # tylko ADMIN
    async def delete(self, user_id: UUID) -> None: ...   # tylko ADMIN
    async def change_password(self, user_id: UUID, new_password: str) -> None: ...
```

`UserService` przyjmuje `UserRepository` przez konstruktor (dependency injection) — nie importuje infra bezpośrednio.

### 5. Rozszerzyć `auth.py` o refresh token

`auth.py` zostaje, ale `authenticate` wywołuje `UserService`, nie `user_store`. Usunąć import `user_store` z routera.

Dodać obsługę refresh tokenów:

```python
def create_access_token(user: User) -> str:
    """Krótkożyjący JWT (15 min) — nosi user_id, email, role."""
    ...

def create_refresh_token(user: User) -> str:
    """Długożyjący JWT (30 dni) — nosi tylko user_id, typ 'refresh'."""
    ...

def verify_refresh_token(token: str) -> UUID:
    """Weryfikuje refresh token i zwraca user_id."""
    ...
```

Access token i refresh token to dwa osobne tokeny z różnym `exp` i różnym `type` w payload. Weryfikacja refresh tokenu sprawdza `type == "refresh"` żeby nie można było użyć access tokenu jako refresh.

### 5a. `RefreshTokenRepository` — blacklist w Redis

Refresh tokeny muszą być unieważnialne (logout). Blacklist w Redis — klucz to `jti` (JWT ID) tokenu, TTL równy czasowi życia tokenu:

```python
# infrastructure/token_store.py
class RefreshTokenStore:
    async def revoke(self, jti: str, ttl_seconds: int) -> None: ...
    async def is_revoked(self, jti: str) -> bool: ...
```

Każdy refresh token dostaje unikalny `jti` (UUID) w payload. Przy `/auth/logout` — `jti` trafia do Redis. Przy `/auth/refresh` — sprawdzamy czy `jti` nie jest na blackliście.

---

## Warstwa infrastructure (`gateway/src/infrastructure/`)

### 6. Rozszerzyć `UserRepository`

Dodać brakujące metody:

```python
async def find_all(self) -> list[UserModel]: ...
async def delete(self, user_id: UUID) -> None: ...
async def update_password(self, user_id: UUID, hashed: str) -> None: ...
```

### 7. Rozszerzyć `AnalysisRepository`

Dodać scoping do użytkownika i historię:

```python
async def find_by_task_id(self, task_id: str) -> AnalysisModel | None: ...
async def find_by_user(self, user_id: UUID) -> list[AnalysisModel]: ...
async def find_by_user_and_id(self, user_id: UUID, analysis_id: UUID) -> AnalysisModel | None: ...
```

`find_by_user_and_id` — używane przy `GET /analysis/{task_id}` żeby zweryfikować własność.

### 8. Dodać `task_id` do `AnalysisModel`

Aktualnie model przechowuje `evaluation_id`, ale nie Celery `task_id`, przez co nie można wyszukać rekordu po `task_id` zwróconym klientowi:

```python
# models.py
task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
```

→ Wymagana migracja Alembic.

### 9. Usunąć `user_store.py`

Po migracji loginu na bazę — plik do usunięcia.

### 10. Audit log — `LoginEventModel`

Nowa tabela `login_events` do śledzenia aktywności:

```python
class LoginEventModel(Base):
    __tablename__ = "login_events"

    id: Mapped[uuid.UUID]
    user_id: Mapped[uuid.UUID | None]   # None przy nieudanej próbie (nieznany email)
    email: Mapped[str]
    success: Mapped[bool]
    ip_address: Mapped[str]
    user_agent: Mapped[str | None]
    created_at: Mapped[datetime]
```

`LoginEventRepository` z jedną metodą `save()`. Router przekazuje `Request` do logowania — FastAPI udostępnia `request.client.host` (IP) i `request.headers.get("user-agent")`.

Admin powinien mieć dostęp do historii przez `GET /admin/login-events` z filtrowaniem po `user_id` i `success`.

→ Wymagana migracja Alembic: `add_login_events_table`.

---

## Endpointy — nowe i zmienione (`router.py`)

### Auth

| Metoda | Ścieżka | Kto | Opis |
|---|---|---|---|
| `POST` | `/auth/login` | wszyscy | Zwraca access token w body, refresh token w `httpOnly cookie` |
| `POST` | `/auth/refresh` | wszyscy | Czyta refresh token z cookie, zwraca nowy access token |
| `POST` | `/auth/logout` | zalogowany | Unieważnia refresh token (wpisuje `jti` do Redis blacklist) |

**Ważne — `httpOnly cookie`:**
- Refresh token nigdy nie trafia do JavaScript — ustawiony przez `Set-Cookie: refresh_token=...; HttpOnly; Secure; SameSite=Strict`
- Access token zwracany w body JSON (krótki czas życia, bezpieczny w `memory` frontendu, nie `localStorage`)
- FastAPI ustawia cookie przez `response.set_cookie(...)` w endpoincie login/refresh

### Rejestracja i CRUD użytkowników

| Metoda | Ścieżka | Kto | Opis |
|---|---|---|---|
| `POST` | `/users` | ADMIN | Rejestracja nowego użytkownika |
| `GET` | `/users` | ADMIN | Lista wszystkich użytkowników |
| `GET` | `/users/me` | każdy | Profil zalogowanego użytkownika |
| `DELETE` | `/users/{user_id}` | ADMIN | Usunięcie użytkownika |
| `PATCH` | `/users/me/password` | każdy | Zmiana własnego hasła |

### Historia analiz

| Metoda | Ścieżka | Kto | Opis |
|---|---|---|---|
| `GET` | `/analysis` | każdy | Historia analiz zalogowanego użytkownika |
| `GET` | `/analysis/{task_id}` | właściciel / ADMIN | Status i wynik — ze sprawdzeniem własności |

### Zmiana w `POST /analysis`

Zapisać do bazy `AnalysisModel` z `user_id` i `task_id` zaraz po wysłaniu do Celery — teraz tego nie robi.

---

## Migracje Alembic

1. `add_task_id_to_analyses` — dodanie kolumny `task_id` z indeksem do tabeli `analyses`
2. `add_login_events_table` — nowa tabela audit logu
3. `seed_admin_user` — domyślne konto admina przy pierwszym starcie systemu. Dane czytane ze zmiennych środowiskowych, nie hardkodowane w migracji:
   ```bash
   # .env.example
   ADMIN_EMAIL=admin@corvus.local
   ADMIN_PASSWORD=                  # uzupełnij przed pierwszym startem
   ```
   Migracja sprawdza czy admin już istnieje (`SELECT` po emailu) — jeśli tak, pomija seed. Dzięki temu jest idempotentna i bezpieczna przy kolejnych `alembic upgrade head`.

---

## Kolejność implementacji

1. Migracje Alembic: `task_id` w `analyses` + `login_events` + seed admina
2. Rozszerzyć `UserRepository` i `AnalysisRepository`
3. Dodać `RefreshTokenStore` (Redis blacklist)
4. Dodać `LoginEventRepository`
5. Napisać `UserService` (application layer)
6. Rozszerzyć `auth.py` — `create_access_token`, `create_refresh_token`, `verify_refresh_token`
7. Zmienić `POST /auth/login` — używa `UserService`, ustawia `httpOnly cookie`, zapisuje `LoginEvent`
8. Dodać `POST /auth/refresh` i `POST /auth/logout`
9. Dodać endpointy CRUD użytkowników
10. Naprawić `POST /analysis` — zapis do DB po enqueue
11. Naprawić `GET /analysis/{task_id}` — scoping do usera
12. Dodać `GET /analysis` — historia
13. Dodać `GET /admin/login-events`
14. Usunąć `user_store.py`
15. Testy jednostkowe `UserService`, `auth.py` + integracyjne endpointów
