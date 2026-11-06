#!/usr/bin/env bash
# Every five minutes: is Corvus working, and did it log anything that needs a
# person? The answer goes to a dead man's switch (healthchecks.io or alike).
#
#   ok       → ping WATCH_PING_URL            (a missing ping is the alarm:
#                                              the server, cron or this script
#                                              is down)
#   problem  → ping WATCH_PING_URL/fail with what was found in the body
#
# What counts as a problem:
#   - /health reports anything but "ok" — the agent or the Celery worker is
#     down, which leaves actions pending with nothing else showing it;
#   - a log event that means the app chose availability over correctness and
#     a person should know: a worker that could not write an action's status
#     (`task_status_write_failed`), and revoked tokens accepted while Redis
#     was away (`token_store_check_failed_fail_open`);
#   - an action the promoter lost to the worker rather than to the model: one
#     whose run kept killing the worker (`task_delivered_too_often`), and one
#     that stopped moving and was given up (`action_abandoned`).
#
# Run by cron (setup-server.sh installs it); by hand: ./watch.sh
set -euo pipefail

cd "$(dirname "$0")"
set -a
# shellcheck disable=SC1091
. ./.env
set +a

if [ -z "${WATCH_PING_URL:-}" ]; then
    echo "watch: WATCH_PING_URL is empty — nobody would hear about a problem" >&2
    exit 1
fi

COMPOSE=(docker compose -f docker-compose.prod.yml)
# A little over the cron period, so an event logged between two runs is seen
# by one of them; seen twice is fine, missed is not.
SINCE=6m
EVENTS='task_status_write_failed|token_store_check_failed_fail_open|task_delivered_too_often|action_abandoned'

problems=""

health="$(curl -fsS -m 10 "https://${CORVUS_DOMAIN}/api/health" 2>&1 || true)"
if ! printf '%s' "$health" | grep -q '"status":"ok"'; then
    problems+="health: ${health:-no answer}"$'\n'
fi

found="$(IMAGE_TAG="$(cat .deployed-tag)" "${COMPOSE[@]}" logs --no-color \
    --since "$SINCE" app agent agent-worker 2>&1 | grep -E "$EVENTS" | tail -20 || true)"
if [ -n "$found" ]; then
    problems+="log events in the last ${SINCE}:"$'\n'"$found"$'\n'
fi

if [ -n "$problems" ]; then
    echo "watch: $(date -u +%FT%TZ) problem" >&2
    printf '%s' "$problems" >&2
    # The body shows up in the alert, so whoever reads it knows where to look.
    printf '%s' "$problems" | head -c 10000 \
        | curl -fsS -m 10 --retry 3 --data-binary @- "${WATCH_PING_URL}/fail" >/dev/null
    exit 1
fi

curl -fsS -m 10 --retry 3 "$WATCH_PING_URL" >/dev/null
