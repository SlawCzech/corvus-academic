# ADR 0022: Every action runs on a provider's key

- Status: Accepted
- Date: 2026-11-03
- Supersedes: [ADR 0004](0004-self-hosted-default-model-with-byok.md) (the self-hosted default), [ADR 0007](0007-admin-managed-local-model-allowlist.md) (the admin's model allowlist), [ADR 0016](0016-local-chat-models-are-off-by-default.md) (the switch that hid local models)
- Amends: [ADR 0011](0011-a-key-per-provider-chosen-per-action.md) (no provider is no longer "the local model"), [ADR 0013](0013-a-server-without-local-models.md)

## Context

ADR 0016 turned local chat models off by default and kept their code, tests and evals "in case". A month on, nothing has used them: production never had them (ADR 0013), prompts are tuned and measured on Claude, and the user has said every check runs on the cloud. ADR 0021 removed the last Ollama container.

What the hidden path still cost was real. `app` kept a model allowlist with its own table, admin page and permission, a `LOCAL_MODELS_ENABLED` switch on every action, and a `model` argument threaded from the frontend to every node. The agent kept a reading budget per node, so each node had two prompts: a whole thesis for a hosted model and an excerpt with a map and warning rules for the local one. The evals defaulted to `qwen3`. Every change to a node had to keep a path alive that no one ran.

Corvus is a working app now, not a learning exercise. A path no one runs is a path no one tests.

## Decision

- **An action names a provider, always.** `POST /students/{id}/actions` without `provider` is a 409, the shape ADR 0013 gave a server with the switch off. A provider without a stored key stays a 409 too (ADR 0011).
- **The agent has no model of its own.** `get_llm()` returns the promoter's provider model or raises; `MODEL_BACKEND`, `OLLAMA_*` and the service's `ANTHROPIC_API_KEY` go. `GET /models` reports only the model each provider runs on.
- **Nodes read the whole thesis.** The reading budgets, the excerpt rules and the chapter splitting existed for a small context; the counts code computes (body length, bibliography entries) still travel with the text.
- **The allowlist goes.** `model_policy`, `model_service`, `models_router`'s admin routes, the ORM model of `mentoring.model_settings` (the table is dropped in the next release, so a rolled-back image still finds it), `MANAGE_MODELS`, `LOCAL_MODELS_ENABLED`, and the admin's model page in the frontend.
- **Evals run on a provider.** `--model` is `claude` or `openai`; the key comes from the environment, as before.

## Consequences

- A promoter without a key can manage students and upload theses but runs nothing, as on production since ADR 0013.
- The `model` argument is still accepted by `run_action` and ignored, so tasks queued by an older `app` during a deploy still run.
- Bringing a local model back would be new work: a model, a reading budget if its context is small, and evals on it. ADR 0004's privacy argument is answered by the promoter choosing the provider, not by Corvus.
