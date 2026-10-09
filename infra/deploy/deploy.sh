#!/usr/bin/env bash
# Roll the server to the images of one commit, or back if they do not come up.
#
#   ./deploy.sh <git-sha>      deploy that commit's images (CD calls this)
#   ./deploy.sh rollback       go back to the previously deployed commit
#
# Pulling needs a GHCR login; CD logs in for the length of one deploy. By
# hand, the simpler road back is GitHub → Actions → the older "Deploy" run →
# "Re-run all jobs", which deploys that commit again.
#
# Database migrations run in the app and agent entrypoints, before they start
# serving; a migration that fails leaves that container unhealthy, and the
# rollback below brings the old images back. Migrations are not undone — an
# old image runs against the new schema, which is fine for additive changes
# and is why destructive ones need a release of their own.
set -euo pipefail

cd "$(dirname "$0")"
COMPOSE=(docker compose -f docker-compose.prod.yml)
CURRENT_FILE=.deployed-tag
PREVIOUS_FILE=.previous-tag
WAIT_SECONDS=300

target="${1:?usage: deploy.sh <git-sha> | rollback}"
if [ "$target" = rollback ]; then
    target="$(cat "$PREVIOUS_FILE")"
fi
current="$(cat "$CURRENT_FILE" 2>/dev/null || true)"

healthy() {
    # Every service with a healthcheck reports healthy, and the site answers
    # through Caddy — the path a browser takes.
    local unhealthy
    unhealthy="$("${COMPOSE[@]}" ps --format '{{.Service}} {{.Health}}' \
        | awk '$2 != "" && $2 != "healthy" {print $1}')"
    [ -z "$unhealthy" ] || return 1
    # A container in a crash loop has no health to report — look for it too.
    [ -z "$("${COMPOSE[@]}" ps --status restarting -q)" ] || return 1
    set -a; . ./.env; set +a
    curl -fsS -m 10 "https://${CORVUS_DOMAIN}/api/health" >/dev/null
}

up() {
    IMAGE_TAG="$1" "${COMPOSE[@]}" pull --quiet
    IMAGE_TAG="$1" "${COMPOSE[@]}" up -d --remove-orphans
}

echo "deploy: ${current:-nothing} -> $target"
up "$target"

deadline=$((SECONDS + WAIT_SECONDS))
until healthy; do
    if [ $SECONDS -ge $deadline ]; then
        echo "deploy: $target is not healthy after ${WAIT_SECONDS}s" >&2
        IMAGE_TAG="$target" "${COMPOSE[@]}" ps >&2
        IMAGE_TAG="$target" "${COMPOSE[@]}" logs --tail 50 app agent agent-worker frontend >&2
        if [ -n "$current" ] && [ "$current" != "$target" ]; then
            echo "deploy: rolling back to $current" >&2
            up "$current"
        fi
        exit 1
    fi
    sleep 5
done

if [ "$current" != "$target" ]; then
    [ -n "$current" ] && echo "$current" > "$PREVIOUS_FILE"
    echo "$target" > "$CURRENT_FILE"
fi
# Old images pile up at a few hundred MB each; keep a week's worth.
docker image prune -af --filter "until=168h" >/dev/null
echo "deploy: $target is live"
