# ADR 0003: Keep Postgres for everything, add pgvector for guideline RAG

- Status: Accepted; the retrieval part superseded by [ADR 0021](0021-requirements-go-into-the-prompt-whole.md)
- Date: 2026-09-05

## Context

The mentoring pivot (ADR 0001) needs relational storage for Students, thesis draft versions, meeting notes, and a log of AI-action results — classic relational data with real foreign-key relationships (a note belongs to a student, a student belongs to a promoter). Corvus already runs Postgres 16 with SQLAlchemy 2.0 async + Alembic, proven and tested in both `identity` and `agent`.

Separately, the mentoring actions (especially `check_requirements`/`generate_review`) will eventually want retrieval over university/promoter guidelines instead of stuffing the whole guidelines file into every prompt (today's approach — `agent/src/application/guidelines.py::load_guidelines()` loads a full text file). That calls for embeddings + similarity search.

## Decision

No new datastore is introduced. Postgres remains the only database. When guideline retrieval is built (implementation plan Phase 5), use the **pgvector** Postgres extension for embeddings rather than a dedicated vector database (Pinecone, Weaviate, Chroma, etc.).

The embeddings table lives in `agent`'s own `analysis` schema, not `mentoring` — guidelines are static files `agent` already owns and loads today, and retrieval happens at LLM-call time inside `agent`'s nodes, not in `app`.

## Consequences

- One database technology to operate, back up, and monitor instead of two.
- pgvector's similarity search is less specialized than a dedicated vector DB (no advanced ANN index tuning, sharding, etc.) — acceptable given the guideline corpus size (a handful of university/promoter documents, not millions of vectors).
- If retrieval needs ever outgrow pgvector's capabilities, migrating to a dedicated vector store later is a contained change (the retrieval interface in `guidelines.py` is the seam), not a rewrite of the mentoring or identity data model.
