# ADR 0012: Seal the provider key for the task queue

- Status: Accepted
- Date: 2026-10-03
- Amends: [ADR 0011](0011-a-key-per-provider-chosen-per-action.md) (the key "travels as its own task argument")

## Context

A promoter's provider key reaches the worker as a Celery task argument. ADR 0004 and 0011 kept it out of the graph state and the stored result, but not out of the broker: the message in Redis held the key in plain text.

The technical-debt entry called that exposure "fleeting". It is not. Since ADR 0010 tasks are acknowledged late, so the message stays in Redis, unacknowledged, for the whole run, and for up to two hours (the visibility timeout) if the worker dies. In that window the key can be read by anyone who can read Redis: a `MONITOR` session, an RDB or AOF file on disk, a backup of that file, and Flower, which shows task arguments to whoever opens it.

The debt entry suggested passing a reference instead and letting the worker decrypt the key itself. That would give the worker the identity schema and `FERNET_KEY`, the key to every stored user key. That is a much bigger trust grant than the problem asks for, and it crosses the boundary ADR 0002 drew: `agent` knows nothing about users' stored secrets.

## Decision

- **The agent's API seals the key, and the worker unseals it.** `POST /actions` and `POST /actions/{id}/resume` put `sealed_api_key` (a Fernet token) on the task, not `api_key`. The worker opens it in the task, right before `use_credentials`, and from there nothing changes: ContextVar for the run, never the state.
- **The sealing key is derived, not configured.** Both ends are the agent service (one image, two processes) and already share `JWT_SECRET`. The Fernet key is HKDF-SHA256 of that secret with a purpose label. It is a different key from the one that signs JWTs, and the deployment needs no new secret.
- **A key that will not open fails the task at once.** The status row records why, and the task is not retried, because a retry cannot fix it. It does not fall back to the local model either, since ADR 0011 rules out silent fallbacks.

## Consequences

- Redis, its files and Flower show a Fernet token, not a key. Reading the key now takes Redis *and* `JWT_SECRET`.
- Rotating `JWT_SECRET` fails any task that was queued with a key before the rotation, with a message naming the cause. A paused review is unaffected: its resume brings the key again and is sealed under the new secret.
- A task message from before this change carries `api_key`, which the new worker does not accept. Deploy when no action with a key is queued or running. A paused review is fine, for the reason above.
- Unchanged: the hop from `app` to `agent` (`POST /actions` with the key in the JSON body) is plain HTTP inside the compose network. Sealing it there would need a secret shared across the service boundary. TLS between services would be the proper fix, and it belongs with the deployment, not here.
