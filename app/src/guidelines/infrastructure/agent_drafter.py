"""The agent, seen through the catalog's `RubricDrafter` port.

A few lines of HTTP rather than mentoring's `AgentClient`: the catalog does
not import mentoring, and a draft needs two calls, not the whole client.
"""

from typing import Any, cast
from uuid import UUID

import httpx

from src.guidelines.application.exceptions import DrafterUnavailableError
from src.guidelines.application.rubric_drafting import DraftingStatus, ProviderKey

_TIMEOUT = 30.0


class AgentRubricDrafter:
    """Queue a `draft_rubric` action on the agent and read it back."""

    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def submit(
        self, version_id: UUID, context: dict[str, Any], key: ProviderKey, token: str
    ) -> str:
        payload = {
            "action_id": str(version_id),
            "action_type": "draft_rubric",
            "context": context,
            "byok": {"provider": key.provider, "api_key": key.api_key},
        }
        data = await self._call("POST", "/actions", token, payload)
        return str(data["task_id"])

    async def status(self, task_id: str, token: str) -> DraftingStatus:
        data = await self._call("GET", f"/actions/{task_id}", token)
        result: Any = data.get("result")
        payload = cast(dict[str, Any], result) if isinstance(result, dict) else {}
        output: Any = payload.get("output")
        error: Any = data.get("error")
        return DraftingStatus(
            status=str(data.get("status", "")),
            output=cast(dict[str, Any], output) if isinstance(output, dict) else None,
            error=str(error) if error else None,
        )

    async def _call(
        self,
        method: str,
        path: str,
        token: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._client.request(
                method,
                f"{self._base_url}{path}",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=_TIMEOUT,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DrafterUnavailableError(f"agent {method} {path}: {exc}") from exc
        body: Any = response.json()
        return cast(dict[str, Any], body) if isinstance(body, dict) else {}
