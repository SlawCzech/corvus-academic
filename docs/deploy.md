# Deploy: Corvus na `corvus.saek.dev`

> Jeden VPS (OVHcloud, Kanada), `docker compose`, Caddy z HTTPS, wdrożenie po każdym merge'u
> do `main`. Decyzje: [ADR 0013](adr/0013-a-server-without-local-models.md)
> (bez lokalnych modeli czatu). Pliki serwera: [`infra/deploy/`](../infra/deploy/).

## Jak to wygląda

```
przeglądarka ──https──► Caddy :443 ──► frontend ──► app ──► agent / agent-worker ──► Claude / OpenAI
                         (certyfikat                  │          │                    (klucz promotora)
                          sam się odnawia)          postgres   redis   ollama (tylko embeddingi)

GitHub: PR → CI → merge → CI na main → Deploy: obrazy → GHCR → ssh → deploy.sh
```

Z internetu widać tylko Caddy (porty 80 i 443). Reszta rozmawia ze sobą w sieci
Dockera i nie ma opublikowanych portów.

## Jednorazowe przygotowanie

Kolejność ma znaczenie: DNS musi wskazywać na serwer, zanim Caddy pierwszy raz
poprosi o certyfikat.

### 1. Klucz SSH (na Twoim Macu)

Jeśli nie masz jeszcze klucza (`ls ~/.ssh/id_ed25519.pub`):

```bash
ssh-keygen -t ed25519 -C "slaw.czech@gmail.com"
```

Drugi klucz, osobny, tylko dla GitHub Actions. Nie zakładaj na nim hasła, bo
robot go nie wpisze:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/corvus_deploy -N "" -C "github-actions@corvus"
```

### 2. Serwer: OVHcloud VPS

Wybrany 2026-10-09: **VPS-2** (4 vCPU, 8 GB RAM, 75 GB SSD), Ubuntu 24.04, płatność
miesięczna, bez opcji dodatkowych (kopie robi `backup.sh`, poza OVH).

Dlaczego OVH i dlaczego Kanada: Hetzner po dwóch podwyżkach w 2026 kosztował za
8 GB kilka razy więcej, a jego tania linia była niedostępna. W OVH wszystkie
europejskie lokalizacje VPS były wyprzedane. Kanada (Beauharnois) ma decyzję
Komisji Europejskiej o odpowiednim poziomie ochrony danych, więc RODO jej nie
wyklucza; testerom warto powiedzieć, gdzie stoi serwer. Gdy w UE zwolni się
miejsce, przeprowadzka to ta sama instrukcja i odtworzenie z kopii.

Obrazy budowane są na `linux/amd64`, więc serwer musi być x86 (OVH VPS jest).

IP znajdziesz w panelu: **Bare Metal Cloud → Prywatne serwery wirtualne (VPS)**
→ serwer → **IPv4**. Dalej jako `<IP>`.

Pierwszy użytkownik na OVH to `ubuntu` (nie `root`). Jeśli klucz SSH nie został
dodany przy zamówieniu, zaloguj się hasłem z maila i wyślij klucz:

```bash
ssh-copy-id ubuntu@<IP>
```

### 3. DNS w Cloudflare

Cloudflare → `saek.dev` → **DNS → Records → Add record**:

| Type | Name | IPv4 address | Proxy status |
|---|---|---|---|
| A | `corvus` | `<IP>` | **DNS only** (szara chmurka) |

„DNS only”, bo certyfikat wystawia Caddy na serwerze. Pomarańczowa chmurka
(proxy Cloudflare) też da się zrobić, ale to inna konfiguracja; na start nie.

Sprawdzenie (po kilku minutach):

```bash
dig +short corvus.saek.dev
```

### 4. Przygotowanie serwera

```bash
scp infra/deploy/setup-server.sh ubuntu@<IP>:
```

```bash
ssh ubuntu@<IP> 'sudo bash setup-server.sh'
```

Skrypt na końcu **wypisuje hasło do backupów**. Od razu zapisz je w menedżerze
haseł: bez niego żadna kopia się nie odszyfruje.

Od teraz logujesz się jako `deploy` (logowanie hasłem i na roota jest wyłączone):

```bash
ssh deploy@<IP>
```

Dopisz klucz dla GitHub Actions do `deploy`:

```bash
ssh deploy@<IP> 'cat >> ~/.ssh/authorized_keys' < ~/.ssh/corvus_deploy.pub
```

### 5. Sekrety produkcyjne (na serwerze)

```bash
scp infra/deploy/env.production.example deploy@<IP>:/srv/corvus/.env
```

```bash
ssh deploy@<IP>
```

Na serwerze jedno polecenie losuje sekrety i wpisuje je do pliku:

```bash
cd /srv/corvus && chmod 600 .env && sed -i -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -hex 24)|" -e "s|^JWT_SECRET=.*|JWT_SECRET=$(openssl rand -hex 32)|" -e "s|^FERNET_KEY=.*|FERNET_KEY=$(openssl rand -base64 32 | tr '+/' '-_')|" -e "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=$(openssl rand -base64 18 | tr '+/' '-_')|" .env
```

Ręcznie (`nano .env`) zostają `ADMIN_EMAIL` (inny niż adres Twojego konta
promotora, ADR 0008; nie musi to być działająca skrzynka) i `CROSSREF_MAILTO`.


**`FERNET_KEY`, `POSTGRES_PASSWORD` i `ADMIN_PASSWORD` skopiuj do menedżera haseł.**
Zgubiony `FERNET_KEY` oznacza, że zapisane klucze API testerów stają się
nieodszyfrowywalne, nawet z kopii. Nie używaj wartości z lokalnego `.env`.

### 6. Kopia poza serwerem: Cloudflare R2

Masz już konto Cloudflare, więc R2 jest najprostszy (darmowe 10 GB).

1. Cloudflare → **R2** → Create bucket `corvus-backups` (location hint: Western Europe).
   W ustawieniach bucketu reguła cyklu życia: usuwanie obiektów po 60 dniach.
2. R2 → **Manage API tokens** → Create token: *Object Read & Write*, tylko ten
   bucket. Zapisz *Access Key ID*, *Secret Access Key* i *endpoint*
   (`https://<account-id>.r2.cloudflarestorage.com`).
3. Na serwerze, jako `deploy`. Polecenie zaczyna się od spacji, więc nie trafia
   do historii basha, a `> /dev/null` jest konieczne, bo `rclone config create`
   wypisuje całą konfigurację **razem z sekretem**. R2 nie obsługuje `acl`
   (odpowiada wtedy 501 Not Implemented) i chce `region=auto`:

```bash
 rclone config create r2 s3 provider=Cloudflare access_key_id=<ID> secret_access_key=<SECRET> endpoint=<ENDPOINT> region=auto no_check_bucket=true > /dev/null
```

   Test:

```bash
echo test > /tmp/test.txt && rclone copy /tmp/test.txt r2:corvus-backups && rclone ls r2:corvus-backups && rclone deletefile r2:corvus-backups/test.txt && rm /tmp/test.txt
```

4. W `/srv/corvus/.env`: `BACKUP_REMOTE=r2:corvus-backups`.

Kopie są szyfrowane (gpg) przed wysłaniem, więc R2 widzi tylko zaszyfrowane pliki.

Opcjonalnie: darmowe konto na healthchecks.io, check „daily”, jego URL do
`BACKUP_PING_URL`. Dostaniesz maila, jeśli przez dobę nie przyjdzie żaden
udany backup.

### 7. GitHub

Repo → **Settings → Environments → New environment** `production` → sekrety:

| Sekret | Wartość |
|---|---|
| `DEPLOY_HOST` | `<IP>` |
| `DEPLOY_SSH_KEY` | zawartość `~/.ssh/corvus_deploy` (klucz **prywatny**) |
| `DEPLOY_KNOWN_HOSTS` | wynik `ssh-keyscan -t ed25519 <IP>` |

`DEPLOY_KNOWN_HOSTS` przypina klucz serwera. Jeśli ktoś podszyje się pod IP,
deploy odmówi połączenia.

### 8. Pierwszy deploy

Workflow `Deploy` startuje sam po zielonym CI na `main`. Pierwszy raz można go
uruchomić ręcznie: **Actions → Deploy → Run workflow**. Pierwszy build trwa
dłużej (brak cache), kolejne kilka minut.

Gdy jest zielony, jednorazowo na serwerze wczytaj wytyczne uczelni i ich
embeddingi:

```bash
cd /srv/corvus && export IMAGE_TAG=$(cat .deployed-tag)
docker compose -f docker-compose.prod.yml run --rm app python scripts/seed_guidelines.py
docker compose -f docker-compose.prod.yml run --rm agent python scripts/ingest_guidelines.py
```

Potem `https://corvus.saek.dev`, zaloguj się adminem (`ADMIN_EMAIL` /
`ADMIN_PASSWORD`) i **zrób pierwszy backup ręcznie**: `/srv/corvus/backup.sh`.

### 9. Konta testerów

Admin → **Użytkownicy** → dodaj konto z rolą `promotor`. Hasło przekaż testerowi
innym kanałem niż e-mail z loginem. Tester po zalogowaniu:

1. **Profil** → dodaje swój klucz API do Claude albo OpenAI (bez klucza akcje AI
   się nie uruchomią, ADR 0013),
2. **Studenci** → „Wczytaj przykładowych studentów”: siedmioro fikcyjnych
   studentów z pracami do testowania. Usuwa ich, kiedy przejdzie na własne.

Testerom warto powiedzieć wprost: to wersja testowa, prawdziwe prace tylko
zanonimizowane albo za zgodą autora.

## Na co dzień

- **Wdrożenie:** zmiany lokalnie → PR → CI zielone → merge. Po kilku minutach
  nowa wersja działa (Actions → Deploy pokazuje postęp).
- **Coś poszło źle:** jeśli nowa wersja nie wstanie w 5 minut, `deploy.sh` sam
  wraca do poprzedniej, a workflow jest czerwony. Żeby wrócić do starszej wersji
  ręcznie: Actions → Deploy → run tej wersji → **Re-run all jobs**.
- **Migracje** odpalają się przy starcie `app` i `agent`. Cofnięcie wersji ich
  nie cofa: zmiany schematu, które coś usuwają, wypuszczaj osobno, po wersji,
  która już z tej kolumny nie korzysta.
- **Logi:** `ssh deploy@<IP>`, potem
  `cd /srv/corvus && IMAGE_TAG=$(cat .deployed-tag) docker compose -f docker-compose.prod.yml logs -f app agent-worker`.
- **Monitoring:** UptimeRobot (darmowy), monitor HTTP(s) na
  `https://corvus.saek.dev/api/health` co 5 minut. Ten adres odpowiada 200 także
  przy `degraded`, żeby brak workera nie cofał deployu, więc martwy worker wychodzi
  dopiero w body: monitor typu Keyword na `"status":"ok"`.

## Odtworzenie z kopii

Kopie: `/srv/corvus/backups/` (14 dni) i bucket R2.

**Próba odtworzenia, raz po uruchomieniu i potem co jakiś czas.** Do osobnej bazy,
produkcja nietknięta:

```bash
cd /srv/corvus && export IMAGE_TAG=$(cat .deployed-tag)
C="docker compose -f docker-compose.prod.yml exec -T postgres"
LATEST=$(ls -t backups/corvus-*.dump.gpg | head -1)
$C createdb -U corvus restore_test
gpg --batch --passphrase-file .backup-passphrase -d "$LATEST" | $C pg_restore -U corvus -d restore_test
$C psql -U corvus -d restore_test -c "select count(*) from mentoring.students"
$C dropdb -U corvus restore_test
```

**Prawdziwe odtworzenie** (nadpisuje bazę, najpierw zatrzymaj aplikację):

```bash
cd /srv/corvus && export IMAGE_TAG=$(cat .deployed-tag)
docker compose -f docker-compose.prod.yml stop frontend app agent agent-worker
gpg --batch --passphrase-file .backup-passphrase -d backups/corvus-<data>.dump.gpg \
  | docker compose -f docker-compose.prod.yml exec -T postgres pg_restore -U corvus -d corvus --clean --if-exists
docker compose -f docker-compose.prod.yml up -d
```

Kopię z R2 ściągasz przez `rclone copy r2:corvus-backups/<plik> backups/`.
Na nowym serwerze potrzebne są też `.env` (z `FERNET_KEY`!) i hasło do backupów,
oba z menedżera haseł.

## Czego nie robić

- Nie publikuj portów innych usług (`ports:`) w `docker-compose.prod.yml`.
  Docker omija firewall `ufw`, więc opublikowany port Postgresa jest od razu
  w internecie.
- Nie wystawiaj Flowera: pokazuje kolejkę tasków.
- Nie włączaj LangSmith/Langfuse na produkcji: prompty zawierają tekst prac.
- Nie kopiuj produkcyjnego `.env` na laptopa ani do repo.
