# ADR 0007: The admin decides which local models promoters may use

- Status: Accepted
- Date: 2026-09-23
- Extends: [ADR 0004](0004-self-hosted-default-model-with-byok.md)

## Context

ADR 0004 made self-hosted Ollama the default path. In practice the action panel asked promoters to type an Ollama tag by hand (`qwen3:30b-a3b`) — something only whoever set up the server could know. A first fix listed every model installed on the server, but "installed" is not the same as "fit for use": the same Ollama holds experiments, oversized models that would stall the worker, and embedding models that fail on chat requests.

Who runs the server is also who knows which models are worth running, so that choice belongs to an admin, not to each promoter.

## Decision

- **Installing and offering are two different things.** Installing a model is still a server operation (`ollama pull`), outside the app. Offering an installed model to promoters is an admin decision, made in the UI (`/admin/models`). Pulling models from the UI was considered and rejected for now: a download can take tens of minutes and tens of GB, which needs a background job, progress reporting, and failure handling for little gain on a single-server setup.
- **The allowlist lives in `app`**, in `mentoring.model_settings` (name, enabled, is_default). `mentoring` owns AI actions, so it owns the rule about which model an action may name. The agent only reports what is installed (`GET /models`, read from Ollama's `/api/tags`). A model with no row is installed but not offered.
- **Exactly one default, picked by the admin.** When the admin has not picked one, the agent's `OLLAMA_MODEL` stands in as the default, so a fresh install works with no admin visit. Once the admin picks a default, the server one is just another model. The default cannot be disabled until another default is set, and only an installed model can be offered or made default.
- **Enforced in `app` when an action is triggered, not just in the dropdown.** `ActionService.trigger` resolves the requested model against the allowlist before it records anything. An empty request resolves to the admin's default. A model that is not allowed gets a 422 and leaves no failed row in the student's history. Under BYOK the local model is ignored, because the provider's model runs.
- **A saved preference can outlive its model.** The promoter's browser-side default (`corvus:ai-defaults`) may name a model the admin has since withdrawn. The frontend falls back to the default, says which model is no longer available, and drops it from the preference the next time the profile is saved.

## Consequences

- Promoters only ever see models that are installed and approved, and `app` enforces this rule itself instead of trusting the frontend.
- Resolving the model on trigger reads the allowlist but does not call the agent. A model that is enabled but later removed from the server can therefore still be dispatched and fail in the worker. The admin panel shows such models as "Nie ma go już na serwerze" so the admin can act, which we accept instead of an agent round-trip on every action.
- `ActionRequest.model` in the agent now defaults to `OLLAMA_MODEL` instead of a hard-coded tag, so "no model named" means the same thing in `app`'s catalog and in the worker.
