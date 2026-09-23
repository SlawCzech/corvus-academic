"""HTTP client for the `agent` service.

Replaces the transitional `/analysis/*` proxy for everything mentoring: `app`
calls `agent` explicitly, with a context it assembled itself, instead of
forwarding a request it does not understand.
"""

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


@dataclass(frozen=True)
class AgentActionStatus:
    """What the agent reports about one dispatched action."""

    status: str
    result: dict[str, Any] | None
    error: str | None


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
        return AgentActionStatus(
            status=str(data["status"]),
            result=cast(dict[str, Any], result) if isinstance(result, dict) else None,
            error=str(error) if error else None,
        )

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

    @staticmethod
    def _as_dict(response: httpx.Response) -> dict[str, Any]:
        body: Any = response.json()
        if not isinstance(body, dict):
            raise AgentUnavailableError(f"Unexpected agent response: {body!r}")
        return body  # pyright: ignore[reportUnknownVariableType]
