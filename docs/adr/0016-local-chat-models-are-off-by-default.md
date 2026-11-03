# ADR 0016: Local chat models are off by default

- Status: Superseded by [ADR 0022](0022-every-action-runs-on-a-providers-key.md)
- Date: 2026-11-01
- Amends: [ADR 0004](0004-self-hosted-default-model-with-byok.md) (the local model as the default), [ADR 0007](0007-admin-managed-local-model-allowlist.md) (the admin's model page), [ADR 0013](0013-a-server-without-local-models.md) (the switch defaults to on)

## Context

ADR 0013 took local chat models off the production server and left them on as the default everywhere else. That made sense while the local model was the product's default. It no longer is. Production runs only on promoters' keys, a full review takes about 25 minutes on `qwen3` against about 90 seconds on Claude, and prompts are now tuned on Claude first: `review_fragment` went from 3 of 7 to 20 of 21 there, and `qwen3` has not been measured since.

Keeping the local path on as the default costs more than the time. Every surface still explains it, so the product describes two ways of working when only one is real. The landing page went furthest: it told visitors that without a key actions run locally and no data leaves their infrastructure. On production that was false, because a thesis goes to the provider the promoter chose.

## Decision

- **`LOCAL_MODELS_ENABLED` defaults to `false`.** A server, or a developer's machine, gets local chat models only by asking for them. `.env.example` says so. The behaviour when off is ADR 0013's: an action without a provider is a 409 before anything is recorded.
- **Hidden, not removed.** The Ollama chat path, the admin's allowlist and their tests stay, and `LOCAL_MODELS_ENABLED=true` brings them back. Removing them would be a larger change that nothing needs yet, and this decision is cheap to reverse.
- **The admin's model page leaves the menu when the switch is off.** The address still answers and says the switch is off.
- **The product says what is true.** The landing page says that actions run on the promoter's key and that the thesis text goes to the chosen provider. Nothing tells a promoter to fall back on a local model when the switch is off.
- **Embeddings stay local.** ADR 0013's reasoning holds: `nomic-embed-text` is small, fast on CPU, and indexes only the guidelines. The Ollama container stays in both compose files.
- **Prompts are judged on Claude.** A prompt change is measured there first. `qwen3` is not a bar a change has to clear.

## Consequences

- A local stack needs a provider key to run an action, or `LOCAL_MODELS_ENABLED=true` in `.env` to go back to Ollama.
- The test suite runs with the switch on, so the hidden path stays covered. It would rot quietly otherwise.
- A promoter's thesis text always leaves for a provider when an action runs. That reverses the privacy default of ADR 0004, and each promoter's choice of provider now carries that weight. Before real theses go through, the university's view on this needs asking.
- Nothing in the product can run offline by default any more. Anyone who needs that sets the switch and installs a model.
- The eval targets in the `Makefile` still default to `qwen3`, because running them on Claude costs money and needs the key exported. `MODEL=claude` is what a prompt change should use.
