# ADR 0021: Requirements go into the prompt whole

- Status: Accepted
- Date: 2026-11-03
- Supersedes: the retrieval part of [ADR 0003](0003-postgres-pgvector-for-persistence-and-rag.md)
- Amends: [ADR 0013](0013-a-server-without-local-models.md) and [ADR 0016](0016-local-chat-models-are-off-by-default.md) (embeddings stay local)

## Context

Phase 5 built retrieval over the university requirements: `agent` split its two static requirements files into sections, embedded them with `nomic-embed-text` on Ollama, stored them in `analysis.guideline_chunks` (pgvector), and gave an action the sections nearest to the opening of the thesis. ADR 0013 and 0016 kept a small Ollama container on every deployment for that one model.

Two things changed since. ADR 0006 moved guidelines into a catalog in `app`, and a student with a guideline set gets its rubric in the action context; the agent skips its own requirements whenever the context carries `guidelines`. Retrieval therefore ran only for a student without a set. And the files it searched are 4.4 kB and 6.5 kB, which a hosted model takes whole without noticing, while ADR 0016 made hosted models the only ones in use.

What remained was a container, a volume, an ingestion step after every change of the files, a table, two settings and a fallback path, all to pick a few kilobytes out of a few more. Corvus is now run as a working app for a handful of testers, not kept as a learning exercise, so a mechanism has to earn its place by what the app needs.

## Decision

- **The agent's requirements file goes into the prompt whole**, for the actions that need requirements and have no guideline set from `app`. `retrieve_relevant_guidelines` becomes `load_guidelines`.
- **Embeddings go.** `embeddings.py`, `guideline_store.py`, `scripts/ingest_guidelines.py`, `make ingest-guidelines`, the `EMBEDDING_*` and `RAG_TOP_K` settings, and the ORM model of `analysis.guideline_chunks`. The table itself is dropped by a migration in the next release, once no running image reads it: `deploy.sh` rolls back images, not migrations.
- **Ollama leaves the deployments.** Production ran it only for embeddings; the local compose's container served nothing else either.
- **The pgvector image and extension stay.** Migration `0004` creates the extension and imports `pgvector`, so a database built from scratch still needs both. Removing them would mean rewriting history for no gain.

## Consequences

- Nothing in Corvus embeds anything. ADR 0004's reason for local embeddings (keep the thesis text out of anyone's API for indexing) holds trivially: there is no indexing.
- "RAG over the full regulation", the follow-up ADR 0006 listed, is dropped with it. A regulation of tens of pages fits in a hosted model's context; if a document ever does not, retrieval comes back, in-process (`fastembed`) rather than as a container.
- The prompt for a student without a set is a few kilobytes longer. The severity rules no longer need to be pinned, since nothing can drop them.
