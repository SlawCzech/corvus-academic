"""HTTP client for the `agent` service.

Replaces the transitional `/analysis/*` proxy for everything mentoring: `app`
calls `agent` explicitly, with a context it assembled itself, instead of
forwarding a request it does not understand.
"""

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

import httpx
import structlog

from src.mentoring.application.exceptions import AgentUnavailableError

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_TIMEOUT = 30.0


@dataclass(frozen=True)
class BYOK:
    """The caller's own provider key, sent for one action only.

    Never persisted on this side of the wire and never logged: `app` decrypts
    it per request, hands it over, and forgets it.
    """

    provider: str
    api_key: str


# Decrypts the caller's stored key for one provider, or returns None when
# they have none. Called only once it is known which provider a run needs,
# so nobody's key is decrypted for a run that will not use it.
KeyLoader = Callable[[str], Awaitable[BYOK | None]]


@dataclass(frozen=True)
class AgentActionStatus:
    """What the agent reports about one dispatched action."""

    status: str
    result: dict[str, Any] | None
    error: str | None
    # The graph's steps and the ones done, while the action runs.
    progress: dict[str, Any] | None = None
    # Set when the promoter can fix the failure themselves — no credits on
    # the provider account, a refused key. Opaque here: the frontend reads it.
    error_code: str | None = None
    # Tokens spent so far — totals and by model — as the agent counts them.
    usage: dict[str, Any] | None = None


class StatusCache:
    """The agent's last answer per task, reused for a moment.

    Polling an action reaches the agent on every call. The UI asks every
    three seconds; a client that asks faster, or ten tabs on the same action,
    get the same answer instead of as many requests to the agent. Shared by
    the whole process, so it outlives the per-request client.
    """

    def __init__(
        self, ttl_seconds: float = 2.0, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._entries: dict[str, tuple[float, AgentActionStatus]] = {}

    def get(self, task_id: str) -> AgentActionStatus | None:
        entry = self._entries.get(task_id)
        if entry is None or self._clock() - entry[0] >= self._ttl:
            return None
        return entry[1]

    def put(self, task_id: str, status: AgentActionStatus) -> None:
        now = self._clock()
        # Expired entries go on every write: the cache holds a few seconds of
        # polling, never every task the process has seen.
        self._entries = {
            k: v for k, v in self._entries.items() if now - v[0] < self._ttl
        }
        self._entries[task_id] = (now, status)

    def forget(self, task_id: str) -> None:
        self._entries.pop(task_id, None)


class AgentClient:
    """Thin typed wrapper over the agent's `/actions` endpoints."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        statuses: StatusCache | None = None,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._statuses = statuses

    async def submit_action(
        self,
        action_id: UUID,
        action_type: str,
        student_id: UUID,
        context: dict[str, Any],
        token: str,
        model: str | None = None,
        language: str = "pl",
        byok: BYOK | None = None,
    ) -> str:
        """Queue an action and return the agent's task id."""
        payload: dict[str, Any] = {
            "action_id": str(action_id),
            "action_type": action_type,
            "student_id": str(student_id),
            "context": context,
            "language": language,
        }
        if model is not None:
            payload["model"] = model
        if byok is not None:
            payload["byok"] = {"provider": byok.provider, "api_key": byok.api_key}

        data = await self._post("/actions", payload, token)
        return str(data["task_id"])

    async def get_action(self, task_id: str, token: str) -> AgentActionStatus:
        """Read one action's current status from the agent.

        Answered from the cache when the agent was asked a moment ago.
        """
        if (
            self._statuses is not None
            and (cached := self._statuses.get(task_id)) is not None
        ):
            return cached
        data = await self._get(f"/actions/{task_id}", token)
        result: Any = data.get("result")
        error: Any = data.get("error")
        progress: Any = data.get("progress")
        error_code: Any = data.get("error_code")
        usage: Any = data.get("usage")
        status = AgentActionStatus(
            status=str(data["status"]),
            result=cast(dict[str, Any], result) if isinstance(result, dict) else None,
            error=str(error) if error else None,
            progress=(
                cast(dict[str, Any], progress) if isinstance(progress, dict) else None
            ),
            error_code=str(error_code) if error_code else None,
            usage=cast(dict[str, Any], usage) if isinstance(usage, dict) else None,
        )
        if self._statuses is not None:
            self._statuses.put(task_id, status)
        return status

    async def resume_action(
        self,
        task_id: str,
        decision: dict[str, Any],
        token: str,
        byok: BYOK | None = None,
    ) -> None:
        """Continue a run paused for the promoter, with their decision."""
        payload: dict[str, Any] = {"decision": decision}
        if byok is not None:
            payload["byok"] = {"provider": byok.provider, "api_key": byok.api_key}
        await self._post(f"/actions/{task_id}/resume", payload, token)
        self._forget(task_id)

    async def cancel_action(self, task_id: str, token: str) -> AgentActionStatus:
        """Ask the agent to stop one action; a finished one is left as it is."""
        data = await self._post(f"/actions/{task_id}/cancel", {}, token)
        self._forget(task_id)
        return AgentActionStatus(status=str(data["status"]), result=None, error=None)

    async def delete_action(self, task_id: str, token: str) -> None:
        """Have the agent forget one action; idempotent on its side."""
        await self._delete(f"/actions/{task_id}", token)

    async def delete_student_actions(self, student_id: UUID, token: str) -> None:
        """Have the agent forget every action run for a student."""
        await self._delete(f"/students/{student_id}/actions", token)

    async def list_models(self, token: str) -> dict[str, Any]:
        """The chat models the agent's Ollama has installed, plus BYOK models."""
        return await self._get("/models", token)

    # ---------- transport ----------

    def _forget(self, task_id: str) -> None:
        """Drop a cached status the promoter's own move has just made stale."""
        if self._statuses is not None:
            self._statuses.forget(task_id)

    async def _post(
        self, path: str, payload: dict[str, Any], token: str
    ) -> dict[str, Any]:
        try:
            response = await self._client.post(
                f"{self._base_url}{path}",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=_TIMEOUT,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("agent_request_failed", path=path, error=str(exc))
            raise AgentUnavailableError(str(exc)) from exc
        return self._as_dict(response)

    async def _get(self, path: str, token: str) -> dict[str, Any]:
        try:
            response = await self._client.get(
                f"{self._base_url}{path}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=_TIMEOUT,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("agent_request_failed", path=path, error=str(exc))
            raise AgentUnavailableError(str(exc)) from exc
        return self._as_dict(response)

    async def _delete(self, path: str, token: str) -> None:
        try:
            response = await self._client.delete(
                f"{self._base_url}{path}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=_TIMEOUT,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("agent_request_failed", path=path, error=str(exc))
            raise AgentUnavailableError(str(exc)) from exc

    @staticmethod
    def _as_dict(response: httpx.Response) -> dict[str, Any]:
        body: Any = response.json()
        if not isinstance(body, dict):
            raise AgentUnavailableError(f"Unexpected agent response: {body!r}")
        return body  # pyright: ignore[reportUnknownVariableType]
