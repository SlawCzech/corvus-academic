# ADR 0001: Reframe Corvus as an AI-first student-mentoring platform

- Status: Accepted
- Date: 2026-09-05

## Context

Corvus started as a PoC: upload one thesis PDF/DOCX, run it through a fixed 4-node LangGraph pipeline (structure → methodology → requirements → review), get a review back. The original educational framing (CLAUDE.md, May 2026) was learning a Python + TypeScript microservices stack with DDD.

That original pipeline is closer to "RAG + one structured LLM call" than anything agentic — a deterministic sequence of nodes over a single document, run once. It doesn't need memory, tool use, human-in-the-loop, or multi-step reasoning, because there is no ongoing relationship to reason about.

The user wants to deploy something real — informally, for a handful of trusted colleagues — and wants the educational value to shift toward production AI-app patterns (LangGraph, LangSmith, agentic AI, agentic harnesses) rather than DDD/microservices practice, which was the original priority.

## Decision

Corvus becomes a platform for promoters/reviewers to manage students over the full thesis lifecycle: create students, log meeting notes, and run predefined AI actions against a student's thesis — propose/evaluate a topic, evaluate methodology, check progress and detect changes between draft versions, draft meeting notes, and produce a final formal + substantive review with a score.

This is a genuine architectural pivot, not just new features: it moves Corvus from a stateless batch pipeline to a stateful system with a persistent per-student history, which is what creates real reasons to use tool-calling, structured output with retries, context retrieval, and (eventually) LangSmith eval/tracing — the AI-app patterns the user wants to learn deliberately, not incidentally.

Target deployment: some cloud provider (not yet fixed — see ADR 0002/0006 for infra), for a small trusted user group, not public SaaS and not an official university deployment.

## Consequences

- The original 5-phase session plan in `docs/sessions.md` is superseded past Phase 5.1 (Docker). See `docs/specs/mentoring-platform-implementation-plan.md` for the phased plan that replaces it.
- Educational priority shifts: reuse and depth on LangGraph/structured-output/tool-use patterns matter more than service-boundary purity. See ADR 0002.
- The interface stays deliberately simple (predefined actions, not chat) for v1 — see ADR 0005 — to avoid the largest, most speculative complexity (conversational memory, multi-agent routing) before the simpler shape proves itself.
- This pivot is visible in the git history as a hard scope change. That's treated as a documented, reasoned decision (this ADR, and the sibling ADRs) rather than a discontinuity to hide.
