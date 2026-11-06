# Rejestr kategorii czynności przetwarzania (art. 30 ust. 2 RODO)

> Dokument wewnętrzny usługodawcy, nie do publikacji. Aktualizuj razem z
> regulaminem (`frontend/content/legal/Terms.tsx`) — ten sam stan, inna forma.
> Wersja regulaminu: 2026-11-06. Decyzja: [ADR 0027](adr/0027-corvus-is-the-promoters-processor.md).

## 1. Podmiot przetwarzający

Usługodawca Corvusa (dane: `OPERATOR_NAME`, `OPERATOR_EMAIL` w `/srv/corvus/.env`).
Inspektora ochrony danych nie wyznaczono (art. 37 RODO nie wymaga).

## 2. Administratorzy

Promotorzy z kontem w Corvusie, każdy za dane własnych studentów — albo uczelnie,
w których imieniu działają. Umowa powierzenia: § 5 regulaminu, zawierana
akceptacją; ewidencja w tabeli `identity.terms_acceptances` (użytkownik, wersja,
data).

## 3. Kategorie przetwarzania w imieniu administratorów

| Kategoria | Dane | Gdzie |
|---|---|---|
| Ewidencja studentów | imię i nazwisko, kierunek, typ i temat pracy, obszar i cel badań, status opieki | `mentoring.students` |
| Wersje i fragmenty pracy | plik, wyekstrahowany tekst (ze stroną tytułową), skrót pliku, liczba znaków | `mentoring.thesis_drafts`, `mentoring.thesis_fragments`, `mentoring.draft_files` |
| Notatki ze spotkań | treść, data | `mentoring.meeting_notes` |
| Akcje AI | kontekst wysłany do dostawcy (po pseudonimizacji), wynik, zużycie tokenów | `mentoring.agent_actions`, `analysis.agent_tasks`, checkpointy grafu do zakończenia przebiegu |
| Feedback do fragmentów | werdykt, treść feedbacku | `mentoring.thesis_fragments` |

Kategorie osób: studenci (autorzy prac), osoby wymienione w pracach i notatkach.

## 4. Podprocesorzy i państwa trzecie

| Podmiot | Rola | Miejsce |
|---|---|---|
| OVHcloud | serwer VPS (cała baza) | Beauharnois, Kanada — decyzja KE 2002/2/WE |
| Cloudflare, Inc. (R2) | zaszyfrowane (gpg) kopie bazy, cykl życia 60 dni | Europa Zachodnia (location hint) |

Nie są podprocesorami: Anthropic i OpenAI (umowa promotora, klucz promotora),
Crossref, Biblioteka Narodowa, Open Library (tylko opisy bibliograficzne),
healthchecks.io (bez danych osobowych studentów).

## 5. Okresy przechowywania

- Pliki i tekst wersji niezaakceptowanych: 14 dni po akceptacji wersji finalnej.
- Pliki i tekst wszystkich wersji i fragmentów: 30 dni po zakończeniu opieki albo
  utworzeniu jednorazowej recenzji (`mentoring/domain/retention.py`).
- Notatki, wyniki AI, ewidencja studenta: do usunięcia studenta lub konta.
- Kopie zapasowe: lokalnie 14 dni, w R2 60 dni.

## 6. Środki bezpieczeństwa (art. 32)

Jak w Załączniku 1 regulaminu: HTTPS, otwarte tylko 22/80/443, SSH wyłącznie
kluczem, baza i Redis poza internetem; bcrypt, krótkie odwoływalne sesje, limit
logowań; klucze API szyfrowane (Fernet) i zaszyfrowane w kolejce (ADR 0012);
rozdział ról admin/promotor (ADR 0008); pseudonimizacja przed dostawcą (ADR 0023);
izolowane parsowanie plików; retencja; codzienne szyfrowane kopie z
przetestowanym odtworzeniem; monitoring (`watch.sh`); Dependabot i CI.

## 7. Dane, których administratorem jest usługodawca

Opisane w polityce prywatności (`/privacy`): konta promotorów, logi logowań
(90 dni, `LOGIN_EVENT_RETENTION`), prośby o konto, akceptacje regulaminu, logi
techniczne.

## 8. Naruszenia

Zawiadomienie promotorów bez zbędnej zwłoki, najpóźniej 48 godzin od stwierdzenia
(§ 5 regulaminu): co się stało, jakich danych i kogo dotyczy, co zrobiono.
Promotor (administrator) decyduje o zgłoszeniu do UODO w ciągu 72 godzin.
