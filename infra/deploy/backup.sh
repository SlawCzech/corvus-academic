#!/usr/bin/env bash
# Daily database backup: dump, encrypt, keep a fortnight here, copy off-server.
#
# Everything Corvus keeps is in Postgres — accounts, students, notes, the
# thesis files themselves (SqlFileStore) and the AI results — so one dump is
# the whole backup. It holds personal data, hence encrypted before it is
# written anywhere: gpg, symmetric, with the passphrase in
# /srv/corvus/.backup-passphrase (and in the owner's password manager).
#
# Run by cron (setup-server.sh installs it); by hand: ./backup.sh
# Restore: see docs/deploy.md, "Odtworzenie z kopii".
set -euo pipefail

cd "$(dirname "$0")"
set -a
# shellcheck disable=SC1091
. ./.env
set +a

# The compose file refuses to load without IMAGE_TAG (deploy.sh sets it), and
# cron does not. Without this line every nightly run died before pg_dump, from
# the first deploy until 2026-11-05, and nothing said so.
export IMAGE_TAG="${IMAGE_TAG:-$(cat .deployed-tag)}"

PASSPHRASE_FILE=/srv/corvus/.backup-passphrase
BACKUP_DIR=/srv/corvus/backups
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
STAMP="$(date -u +%Y-%m-%dT%H%MZ)"
OUT="$BACKUP_DIR/corvus-$STAMP.dump.gpg"

mkdir -p "$BACKUP_DIR"
umask 077

# A run that fails leaves no file behind: gpg writes even an empty stream,
# and a 70-byte "backup" next to the real ones is worse than none.
trap 'rm -f "$OUT"' ERR

# -Fc: compressed custom format, restored with pg_restore. Streamed straight
# into gpg, so no unencrypted copy ever lands on disk.
docker compose -f docker-compose.prod.yml exec -T postgres \
    pg_dump -U corvus -d corvus -Fc \
  | gpg --batch --yes --symmetric --cipher-algo AES256 \
        --passphrase-file "$PASSPHRASE_FILE" -o "$OUT"

# A dump of a few KB means pg_dump failed after the pipe had started.
if [ "$(stat -c %s "$OUT")" -lt 10240 ]; then
    echo "backup: $OUT is suspiciously small — check pg_dump" >&2
    rm -f "$OUT"
    exit 1
fi
# From here the dump is good: an rclone failure must not take it with it.
trap - ERR

find "$BACKUP_DIR" -name 'corvus-*.dump.gpg' -mtime +"$KEEP_DAYS" -delete

if [ -n "${BACKUP_REMOTE:-}" ]; then
    rclone copy "$OUT" "$BACKUP_REMOTE" --quiet
else
    echo "backup: BACKUP_REMOTE is empty — the dump stays on this server only" >&2
fi

echo "backup: $OUT ($(du -h "$OUT" | cut -f1))"

# Optional dead man's switch (e.g. healthchecks.io): reached only when every
# step above succeeded, so a missing ping is the alarm.
if [ -n "${BACKUP_PING_URL:-}" ]; then
    curl -fsS -m 10 --retry 3 "$BACKUP_PING_URL" >/dev/null
fi
