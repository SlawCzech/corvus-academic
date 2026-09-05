# ADR 0005: Predefined agent actions instead of open-ended chat (v1)

- Status: Accepted
- Date: 2026-09-05

## Context

The mentoring pivot (ADR 0001) could be built as either an open-ended chat interface (promoter converses freely with an LLM about a student) or a set of predefined, repeatable actions (promoter clicks "evaluate methodology", optionally adds a free-text detail, gets a structured result). These imply materially different agent architectures: chat needs persistent conversation memory (LangGraph checkpointer/threads) and benefits from a multi-agent-supervisor pattern to route open-ended requests to the right specialist; predefined actions don't, because the caller already knows which action/specialist to invoke.

The user wants the interface to stay simple for v1, with room to add a chat mode later if the predefined-actions approach proves insufficient.

## Decision

v1 ships predefined, repeatable actions only: propose/evaluate topic, evaluate methodology, check progress/detect changes, draft a meeting note, generate final review. Each optionally accepts a short free-text "detail" from the user. No conversational memory, no LangGraph checkpointer/threads, no multi-agent-supervisor routing.

To keep the door open for a future chat mode without a rewrite: context-gathering logic (fetching guidelines, prior student history, draft versions) is implemented as standalone functions keyed by student/action parameters (`app`'s `mentoring/application/context.py`, one function per action type), not embedded inline in request-handling code. A future chat agent can call these same functions as tools.

Human-in-the-loop is handled as "LLM drafts → promoter reviews/edits before it's saved as fact" (a UI/workflow pattern), not as an in-graph LangGraph `interrupt()` — simpler, and sufficient because actions are already bounded, single-purpose calls rather than multi-step conversations that might need to pause mid-way.

## Consequences

- Faster to build and easier to reason about/test for v1 — each action is one bounded, mockable graph run.
- Defers real learning value around conversational agent memory and multi-agent orchestration — acceptable, since ADR 0001's stated preference is depth on one pattern before breadth across several.
- If chat is added later, the context-gathering functions are reusable, but the request/response contract, UI, and possibly the LangGraph state shape (`ActionState`) will need extension to support multi-turn state — this ADR does not pre-design that.
