# ADR 0013: A server without local models

- Status: Accepted
- Date: 2026-10-09
- Amends: [ADR 0004](0004-self-hosted-default-model-with-byok.md) (the local model as the default), [ADR 0007](0007-admin-managed-local-model-allowlist.md) (the allowlist always has a default), [ADR 0011](0011-a-key-per-provider-chosen-per-action.md) (no provider means local)

## Context

Corvus goes on the internet for a handful of testers, on a rented VPS without a GPU. A chat model on its CPU is not a slow option but no option: a review that takes ten minutes on a Mac with unified memory takes an hour or more there, and a 30B model does not fit in the RAM a small VPS has at all.

The code could not say "no local models". ADR 0007's policy always has a default — the admin's or, failing that, the agent's `OLLAMA_MODEL` — and ADR 0011 makes "no provider" mean "that default". On such a server an action without a key would be accepted, queued, and fail (or hang) on a model that is not there.

The embedding model is a different matter. `nomic-embed-text` is ~300 MB and fast on CPU, and it is what keeps the thesis text out of anyone's API for indexing (ADR 0004). It stays.

## Decision

- **`LOCAL_MODELS_ENABLED` (app setting, default `true`).** Off, the server offers no local chat models. Local development keeps the default and changes nothing.
- **Off, an action needs a provider.** `POST /students/{id}/actions` without `provider` is a 409 before anything is recorded or dispatched — the same shape as asking for a provider without a key. Never a silent run on a model that is not there, and never a pick of a key on the promoter's behalf by the server.
- **The catalog says so.** `GET /models` and `GET /models/admin` carry `local_enabled`. Promoters get no local options; the admin's model page says the switch is off instead of listing models nobody can use.
- **The frontend picks a stored key, or nothing.** Nothing chosen resolves to a stored key (Claude before OpenAI), as before. A saved local preference counts as no choice. A saved provider whose key is gone is not swapped for the other provider (ADR 0011's reason) — the run button is disabled and the panel links to the profile to add a key.
- **Embeddings stay local.** A small Ollama with only `nomic-embed-text` runs inside the deployment's network, unreachable from outside and invisible to promoters.

## Consequences

- A tester without a key can browse, add students and upload theses, but runs nothing until they add one. That is the deal on this server: their key, their bill.
- The agent still reports installed Ollama models and still falls back to `OLLAMA_MODEL` when asked for nothing; `app` is what stops such a request. Anything that talks to the agent directly bypasses the switch — nothing does, and the agent is not reachable from outside.
- Moving the embeddings into the worker process (e.g. `fastembed`) would drop the Ollama container entirely. Not done yet: it changes the vectors, which means re-ingesting the guidelines.
