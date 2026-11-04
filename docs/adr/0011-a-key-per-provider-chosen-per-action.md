# ADR 0011: A key per provider, and the promoter picks per action

- Status: Accepted; amended by [ADR 0022](0022-every-action-runs-on-a-providers-key.md) (no provider is a 409)
- Date: 2026-10-01
- Amends: [ADR 0004](0004-self-hosted-default-model-with-byok.md) (the rule that a stored key takes priority)

## Context

ADR 0004 gave each promoter one key, and that key won: with a key stored, every action went to that provider. Two things followed that nobody chose.

- **One key meant one provider.** The key lived in two columns on `identity.users`, so saving an OpenAI key overwrote the Anthropic one. Comparing two providers on the same thesis meant retyping keys.
- **Holding a key meant paying for everything.** A promoter with a key could not run a cheap action on the local model without deleting the key first. ADR 0004 itself named the missing piece: cheap, frequent actions locally, heavier judgment on a frontier model.

## Decision

- **One key per user and provider**, in `identity.user_api_keys` (primary key `user_id, provider`). Saving a key replaces the key for that provider and leaves the other alone; removing is per provider (`DELETE /settings/api-key/{provider}`). The status endpoint lists providers, never keys.
- **The action says what it runs on.** `POST /students/{id}/actions` takes `provider`: one of the caller's providers, or nothing for the self-hosted model. `app` no longer infers it from the stored keys. **No provider means local, even when a key is stored** — nobody is billed for a run they did not ask to be billed for.
- **A provider without a key is refused, not replaced.** Asking for a provider the caller has no key for is a 409 before anything is recorded or dispatched. Falling back to the local model would answer with a different model than the one asked for, and falling back to the other key would bill an account nobody picked.
- **The key is decrypted only once the provider is known.** Endpoints that dispatch work get a loader, not a key; the service calls it for the one provider the run needs. A run on the local model decrypts nothing.
- **The action row keeps the provider's name** (`mentoring.agent_actions.provider`), never the key. A review paused for the promoter resumes on the account it started on; if that key has been removed in the meantime, the resume is a 409 and the review stays paused.
- **The frontend keeps "your key by default".** The choice is one value in the browser-side preference: nothing chosen resolves to a stored key (Claude before OpenAI) or, without one, to the default local model — so a promoter with a single key sees no change. What the run will go on is shown before it starts. A preference naming a key that is gone falls back to the local model and says so, the same way a withdrawn local model does (ADR 0007).

The agent is unchanged: it already took the key per task and held it in a ContextVar for that run only.

## Consequences

- Both providers can be kept and compared, and a promoter with a key can still run on the local model.
- An API client that sends no `provider` now runs locally where it used to run on the stored key. The only client is the frontend, which always sends it.
- Actions from before `provider` existed have it NULL whatever they ran on. A review started on a key and still paused across the migration resumes on the local model.
- Which model a provider's key runs on is still fixed per provider in the agent (`_BYOK_MODELS`). Picking a model within a provider, and showing what a run cost, are not part of this.
- Downgrading `0004_user_api_keys` puts one key back on the user row; a user holding two keeps the Anthropic one.
