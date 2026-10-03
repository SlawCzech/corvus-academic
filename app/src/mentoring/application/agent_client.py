"""HTTP client for the `agent` service.

Replaces the transitional `/analysis/*` proxy for everything mentoring: `app`
calls `agent` explicitly, with a context it assembled itself, instead of
forwarding a request it does not understand.
"""

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


class AgentClient:
    """Thin typed wrapper over the agent's `/actions` endpoints."""

    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

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
        """Read one action's current status from the agent."""
        data = await self._get(f"/actions/{task_id}", token)
        result: Any = data.get("result")
        error: Any = data.get("error")
        progress: Any = data.get("progress")
        error_code: Any = data.get("error_code")
        usage: Any = data.get("usage")
        return AgentActionStatus(
            status=str(data["status"]),
            result=cast(dict[str, Any], result) if isinstance(result, dict) else None,
            error=str(error) if error else None,
            progress=(
                cast(dict[str, Any], progress) if isinstance(progress, dict) else None
            ),
            error_code=str(error_code) if error_code else None,
            usage=cast(dict[str, Any], usage) if isinstance(usage, dict) else None,
        )

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

    async def cancel_action(self, task_id: str, token: str) -> AgentActionStatus:
        """Ask the agent to stop one action; a finished one is left as it is."""
        data = await self._post(f"/actions/{task_id}/cancel", {}, token)
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
