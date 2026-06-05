# Plan: frontend — user management

## Kontekst

Aktualny stan frontendu:
- Login działa — access token zapisywany w `httpOnly cookie` o nazwie `token`
- Middleware chroni `/admin` i `/analysis` — sprawdza cookie + rolę
- Brak logout, brak refresh tokenu, brak historii analiz
- Brak CRUD użytkowników, brak audit logu
- `lib/auth.ts` zawiera tylko typy i `decodeToken` — zero logiki sesji

---

## 1. Strategia tokenów

Aktualnie access token siedzi w `httpOnly cookie`. To bezpieczne podejście dla architektury Next.js (API routes czytają cookie server-side). **Zostawiamy to podejście**, ale rozdzielamy na dwa cookie:

| Cookie | Zawartość | TTL | Flagi |
|---|---|---|---|
| `access_token` | JWT access token | 15 min | `httpOnly; Secure; SameSite=Lax` |
| `refresh_token` | JWT refresh token | 30 dni | `httpOnly; Secure; SameSite=Lax` |

Zmiana nazwy z `token` → `access_token` dla jasności.

---

## 2. Zmiany w `lib/auth.ts`

Dodać helpery do odczytu roli i sprawdzania expiry (używane w middleware i komponentach):

```typescript
export function isTokenExpired(token: string): boolean { ... }
export function getRole(token: string): string | null { ... }
export function getUserId(token: string): string | null { ... }
```

---

## 3. Nowe API routes (`app/api/`)

### Auth

**`app/api/auth/logout/route.ts`** — `POST`
- Wywołuje `POST /auth/logout` na gateway (unieważnia refresh token w Redis)
- Usuwa oba cookie (`access_token`, `refresh_token`) przez `Set-Cookie` z `maxAge=0`
- Redirect → `/login`

**`app/api/auth/refresh/route.ts`** — `POST`
- Czyta `refresh_token` z cookie
- Wywołuje `POST /auth/refresh` na gateway
- Zapisuje nowy `access_token` w cookie
- Zwraca `{ ok: true }` lub `401`

### Użytkownicy (tylko ADMIN)

**`app/api/users/route.ts`** — `GET` + `POST`
- `GET` → lista użytkowników z gateway `GET /users`
- `POST` → rejestracja nowego użytkownika przez gateway `POST /users`

**`app/api/users/[id]/route.ts`** — `DELETE`
- Usuwa użytkownika przez gateway `DELETE /users/{id}`

**`app/api/users/me/route.ts`** — `GET`
- Profil zalogowanego użytkownika z gateway `GET /users/me`

**`app/api/users/me/password/route.ts`** — `PATCH`
- Zmiana hasła przez gateway `PATCH /users/me/password`

### Historia analiz

**`app/api/analysis/route.ts`** — `GET`
- Lista analiz zalogowanego użytkownika z gateway `GET /analysis`

### Audit log (tylko ADMIN)

**`app/api/admin/login-events/route.ts`** — `GET`
- Pobiera historię logowań z gateway `GET /admin/login-events`

---

## 4. Middleware — obsługa wygasłego tokenu

Aktualny middleware tylko sprawdza obecność cookie. Trzeba dodać obsługę expiry:

```typescript
// middleware.ts
export async function middleware(request: NextRequest) {
  const accessToken = request.cookies.get("access_token")?.value
  const refreshToken = request.cookies.get("refresh_token")?.value

  // brak obu tokenów → login
  if (!accessToken && !refreshToken) {
    return NextResponse.redirect(new URL("/login", request.url))
  }

  // access token wygasł ale jest refresh token → odśwież
  if ((!accessToken || isTokenExpired(accessToken)) && refreshToken) {
    // redirect na /api/auth/refresh z powrotem do oryginalnej ścieżki
    const url = new URL("/api/auth/refresh", request.url)
    url.searchParams.set("redirect", request.nextUrl.pathname)
    return NextResponse.redirect(url)
  }

  // ochrona /admin — tylko ADMIN
  if (pathname.startsWith("/admin")) {
    const role = getRole(accessToken!)
    if (role !== "admin") {
      return NextResponse.redirect(new URL("/login", request.url))
    }
  }

  return NextResponse.next()
}
```

---

## 5. Nowe strony (`app/`)

### `app/admin/users/page.tsx` — zarządzanie użytkownikami

Dostępna tylko dla ADMIN. Zawiera:
- Tabela użytkowników: email, rola, data utworzenia, akcje
- Przycisk "Dodaj użytkownika" → modal z formularzem (email, hasło, rola)
- Przycisk "Usuń" przy każdym użytkowniku (z potwierdzeniem)

### `app/admin/login-events/page.tsx` — audit log

Dostępna tylko dla ADMIN. Zawiera:
- Tabela: email, data, IP, user-agent, sukces/porażka
- Filtr po użytkowniku i wyniku (sukces/porażka)

### `app/analysis/history/page.tsx` — historia analiz

Dostępna dla każdego zalogowanego. Zawiera:
- Tabela: tytuł, autor, data, status, link do wyniku
- Kliknięcie w wiersz → wynik analizy

### `app/profile/page.tsx` — profil użytkownika

Dostępna dla każdego zalogowanego. Zawiera:
- Wyświetlenie email i roli
- Formularz zmiany hasła (stare hasło, nowe hasło, potwierdzenie)

---

## 6. Nowe komponenty (`components/`)

**`components/LogoutButton.tsx`**
Wywołuje `POST /api/auth/logout`, po odpowiedzi czyści stan i redirect → `/login`.

**`components/UserManagementTable.tsx`**
Tabela CRUD użytkowników z modalem dodawania. Używana w `/admin/users`.

**`components/LoginEventsTable.tsx`**
Tabela audit logu z filtrowaniem. Używana w `/admin/login-events`.

**`components/AnalysisHistoryTable.tsx`**
Tabela historii analiz z linkami do wyników. Używana w `/analysis/history`.

**`components/ChangePasswordForm.tsx`**
Formularz zmiany hasła z walidacją Zod. Używany w `/profile`.

---

## 7. Nawigacja — zmiany w `Nav.tsx`

Dodać do paska nawigacji:
- Link "Historia" → `/analysis/history` (dla każdego zalogowanego)
- Link "Profil" → `/profile` (dla każdego zalogowanego)
- Dropdown dla ADMIN: "Użytkownicy" → `/admin/users`, "Logi logowań" → `/admin/login-events`
- Przycisk "Wyloguj" → wywołuje `LogoutButton`

---

## 8. Zmiany w istniejących plikach

**`app/api/auth/login/route.ts`**
- Zmienić nazwę cookie `token` → `access_token`
- Skrócić `maxAge` do 15 minut (było 24h)
- Odebrać `refresh_token` z odpowiedzi gateway i zapisać w osobnym cookie (30 dni)

**`app/api/analyze/route.ts`**
- Zmienić odczyt cookie z `token` → `access_token`

**`app/api/status/[taskId]/route.ts`**
- Zmienić odczyt cookie z `token` → `access_token`

**`app/api/admin/api-key/route.ts`**
- Zmienić odczyt cookie z `token` → `access_token`

**`middleware.ts`**
- Pełna wymiana — patrz punkt 4 powyżej
- Dodać `/profile` i `/analysis/history` do `matcher`

---

## 9. Migracje Alembic (przypomnienie z gateway planu)

Frontend zależy od endpointów które wymagają migracji po stronie gateway:
- `add_login_events_table` — przed implementacją `/admin/login-events`
- `seed_admin_user` — przed pierwszym loginem

---

## Kolejność implementacji

1. Zmienić nazewnictwo cookie (`token` → `access_token`) + dodać `refresh_token` w login route
2. Zaktualizować middleware (expiry check + refresh redirect)
3. Dodać `POST /api/auth/logout` i `POST /api/auth/refresh`
4. Dodać `LogoutButton` i wpiąć w `Nav.tsx`
5. Dodać `GET /api/users/me` + stronę `/profile` z `ChangePasswordForm`
6. Dodać `/api/users` + `/api/users/[id]` + stronę `/admin/users` z `UserManagementTable`
7. Dodać `/api/analysis` (historia) + stronę `/analysis/history`
8. Dodać `/api/admin/login-events` + stronę `/admin/login-events`
9. Zaktualizować testy (middleware, login route, nowe komponenty)
