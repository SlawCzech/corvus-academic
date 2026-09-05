# ADR 0004: Self-hosted model as the privacy-preserving default, BYOK as opt-in

- Status: Accepted
- Date: 2026-09-05

## Context

Corvus will hold real (if informal) student data — names, thesis text, meeting notes — for a small trusted user group. Sending that data to a third-party LLM API (Anthropic, OpenAI) raises data-processor/RODO questions the user does not want to solve centrally for an informal, small-scale tool. At the same time, some actions (e.g. the final substantive review) benefit from stronger frontier models than a small self-hosted model can match.

Corvus already has the infrastructure for both paths: `agent/src/infrastructure/llm_factory.py::get_llm()` selects a backend via `MODEL_BACKEND` (ollama/claude/openai), and `identity`'s `UserModel.api_key_encrypted` + `SecretService` (Fernet) already exist for storing a user-supplied key — but neither BYOK path is actually wired into model selection today, and `PATCH /settings/api-key` is currently admin-only.

## Decision

- **Self-hosted Ollama is the default and the privacy-preserving option**: when a user has not supplied their own key, actions run against a locally-run open-weights model (e.g. Gemma, Qwen). Data never leaves infrastructure the user controls.
- **BYOK (bring your own key) is opt-in, per user**: any promoter (not just admins — this requires loosening today's `require_admin` restriction on `PATCH /settings/api-key`) can supply their own Anthropic or OpenAI API key. When present, it takes priority over the Ollama default for that user's actions. Sending data to a third-party API under BYOK is that user's own choice and own account responsibility — Corvus does not hold or pay for a shared key.
- A future refinement (not required for v1) is per-action-type tiering: cheap/frequent actions on the local model, heavier judgment calls (e.g. final review) on a BYOK frontier model when available.
- The API key is passed to `agent`'s Celery task as a plain task parameter, never placed inside the LangGraph state dict — state gets serialized wholesale into persisted action results, so keeping the key structurally separate prevents it from ever leaking into stored output.

## Consequences

- No central compliance burden for third-party data processing — each BYOK user consents individually by supplying their own key.
- Self-hosted models are weaker than frontier APIs for nuanced judgment (e.g. methodology critique) — accepted as the default trade-off for the free/no-key path; users who want better quality opt in via BYOK.
- Running a capable enough local model still costs real compute (a persistent or on-demand GPU/CPU host) — left as a deployment-time decision (implementation plan Phase 6), not resolved here.
