# Przed otwarciem na 10–20 promotorów

> Ostatni krok przed produkcją dla szerszego grona: gałąź `claude/gdpr-terms`
> (regulamin z umową powierzenia, akceptacja, mniej danych — ADR 0027).
> Commity czekają lokalnie, gotowe do wypchnięcia. Odhaczaj po kolei.

## Zanim wypchniesz gałąź

- [x] **Alias pocztowy.** Cloudflare → `saek.dev` → Email → Email Routing:
      włącz routing (Cloudflare doda rekordy MX/TXT), dodaj adres docelowy (Twoja
      skrzynka, potwierdź mailem), utwórz regułę `rodo@saek.dev` → ta skrzynka.
      Wyślij testowy mail na alias.
- [ ] **Dane usługodawcy na serwerze** — w `/srv/corvus/.env`:
      `OPERATOR_NAME="Imię Nazwisko"` (**w cudzysłowie** — bez niego bash
      w `backup.sh`, `watch.sh` i `deploy.sh` potknie się na spacji),
      `OPERATOR_EMAIL=rodo@saek.dev`. Bez restartu: deploy i tak stawia frontend od nowa.
- [ ] **Przeczytaj `/terms` i `/privacy`** (lokalnie albo w podglądzie PR-a), najlepiej
      z kimś, kto zna RODO. To projekty napisane z kodu, nie porada prawna.
- [ ] **Uprzedź testerów**: retencja się skraca, a pierwszy przebieg po deployu
      od razu usunie pliki i tekst prac, które już łapią się pod nowe terminy
      (niezaakceptowane wersje 14 dni po akceptacji, wszystko 30 dni po zamknięciu
      studenta, jednorazówki starsze niż 30 dni). Kto czegoś potrzebuje, niech pobierze.
- [ ] **Ręczny backup** tuż przed merge'em: `/srv/corvus/backup.sh`. Migracja
      czyści numery indeksu, retencja kasuje pliki — cofnąć to można tylko z kopii.

## Wypchnięcie

- [ ] Push `claude/gdpr-terms`, PR, zielone CI, merge → deploy sam.

## Po deployu

- [ ] `https://corvus.saek.dev/terms`: Twoje imię i nazwisko, przycisk „pokaż adres
      e-mail” odsłania alias (nie `[… — OPERATOR_NAME]`).
- [ ] Konto promotora: po zalogowaniu od razu regulamin do akceptacji, po kliknięciu
      dashboard.
- [ ] Testerzy akceptują raz, przy pierwszym wejściu.

## Zaraz potem

- [ ] Mały PR: usunięcie kolumny `mentoring.students.index_number` (dopiero gdy
      ta wersja stoi na produkcji, żeby rollback znalazł kolumnę).
- [ ] Zmiana regulaminu w przyszłości = nowa data w `app/src/identity/domain/terms.py`
      **i** `frontend/content/legal/version.ts` → wszyscy akceptują jeszcze raz.
      Zwykły merge niczego nie wymusza.
