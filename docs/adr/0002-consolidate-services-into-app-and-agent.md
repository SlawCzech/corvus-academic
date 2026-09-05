# ADR 0002: Consolidate 4 microservices into 2 (`app` + `agent`)

- Status: Accepted
- Date: 2026-09-05

## Context

Corvus currently runs 4 Python services plus supporting infrastructure (12 containers total): `gateway` (pure reverse proxy, no domain logic or database), `identity` (auth, users, roles/permissions, audit log, own Postgres schema), `parser` (stateless PDF/DOCX extraction), and `agent` (LangGraph + Celery, own Postgres schema, own HTTP API).

This service-per-bounded-context split was valuable for learning DDD and inter-service communication (see original CLAUDE.md, section 3.2). Following ADR 0001, that is no longer the primary educational goal. Concretely:

- `gateway` does no JWT verification at all — it is a dumb `httpx` proxy (`gateway/src/infrastructure/router.py`). It adds a network hop and an ops surface (its own container, health check, Dockerfile) for zero business logic.
- `identity` and `parser` are both fast, synchronous, low-latency concerns with no reason to be network-isolated from each other for a handful of trusted users.
- The target user base is a few trusted colleagues, informally deployed — not a multi-tenant SaaS needing hard service isolation for scaling or blast-radius reasons.
- Running and deploying 9–12 containers costs real ops time that would otherwise go into the AI/agent code, which is where the actual learning value now lives (ADR 0001).

## Decision

Consolidate into 2 services:

- **`app`** — everything fast/synchronous: identity's domain (auth, users, roles, permissions, audit log), parser's extraction logic (called in-process, no more `/extract` HTTP hop), and the new `mentoring` bounded context (students, meeting notes, thesis draft versions, agent-action log).
- **`agent`** — unchanged in kind: LangGraph + Celery worker + its own HTTP API. This is the only split kept, because it's the only one operationally justified: LLM calls are slow and asynchronous, CRUD is fast and synchronous.

Within `app`, `identity` and the new `mentoring` context stay separate Python subpackages with separate Postgres schemas (`identity`, `mentoring`) and separate Alembic migration lineages — the bounded-context discipline is kept at the code/schema level even though the network boundary is gone. Cross-context references (e.g. `mentoring.students.promotor_id` pointing at an identity user) stay plain UUIDs with no foreign key, following the precedent already set by `agent`'s `AnalysisModel.user_id`.

## Consequences

- Container count drops from ~9-12 to ~5-6 (app, agent, agent-worker, postgres, redis, optionally ollama).
- `gateway`'s proxy code is deleted outright (no logic to preserve — see above). `identity/` and `parser/` are deleted once `app`'s test suite reproduces their combined coverage.
- Losing: independent deploy of identity/parser, and practice with service-to-service auth/proxying. Judged an acceptable trade given ADR 0001's shift in priority.
- If the trusted-user-group scope ever grows into something needing real multi-tenant isolation, `mentoring` and `identity` are already separable subpackages/schemas — re-extraction later is possible without redesign, just re-adding a network boundary.
