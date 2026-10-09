"""Local models: what is installed (agent) meets what is offered (admin).

Promoters see the intersection — installed and enabled. Admins see every
installed model plus any setting whose model has since been removed from the
server, so a stale default is visible instead of silently failing actions.
"""

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from src.mentoring.application.agent_client import AgentClient
from src.mentoring.application.exceptions import ProviderRequiredError
from src.mentoring.domain.model_policy import ModelPolicy
from src.mentoring.infrastructure.repositories import ModelSettingRepository


@dataclass(frozen=True)
class OfferedModel:
    name: str
    parameter_size: str | None


@dataclass(frozen=True)
class PromoterCatalog:
    default: str
    available: list[OfferedModel]
    local_available: bool
    byok: dict[str, str]
    local_enabled: bool = True


@dataclass(frozen=True)
class AdminModelRow:
    name: str
    parameter_size: str | None
    installed: bool
    enabled: bool
    is_default: bool


@dataclass(frozen=True)
class AdminCatalog:
    models: list[AdminModelRow]
    local_available: bool
    server_default: str
    local_enabled: bool = True


@dataclass(frozen=True)
class _Installed:
    models: dict[str, str | None]
    local_available: bool
    server_default: str
    byok: dict[str, str]


class ModelNotInstalledError(Exception):
    """The admin tried to offer a model the server does not have."""


class ModelService:
    def __init__(
        self,
        repo: ModelSettingRepository,
        agent: AgentClient,
        local_enabled: bool = True,
    ) -> None:
        self._repo = repo
        self._agent = agent
        self._local_enabled = local_enabled

    async def _installed(self, token: str) -> _Installed:
        data = await self._agent.list_models(token)
        local = cast(list[dict[str, Any]], data.get("local") or [])
        return _Installed(
            models={str(m["name"]): m.get("parameter_size") for m in local},
            local_available=bool(data.get("local_available")),
            server_default=str(data["default"]),
            byok=cast(dict[str, str], data.get("byok") or {}),
        )

    async def _policy(self, server_default: str) -> ModelPolicy:
        stored = await self._repo.policy()
        return ModelPolicy(settings=stored.settings, server_default=server_default)

    async def resolve(self, requested: str | None) -> str | None:
        """The model an action should name — None leaves it to the agent.

        No agent call here: resolving happens on every action, and the
        admin's choice alone decides what is allowed.

        Raises ProviderRequiredError when the server runs no local models:
        a run that names no provider has nothing left to run on.
        """
        if not self._local_enabled:
            raise ProviderRequiredError
        return (await self._repo.policy()).resolve(requested)

    async def promoter_catalog(self, token: str) -> PromoterCatalog:
        installed = await self._installed(token)
        if not self._local_enabled:
            # The agent is still asked: it alone knows which model each
            # provider key runs on.
            return PromoterCatalog(
                default=installed.server_default,
                available=[],
                local_available=False,
                byok=installed.byok,
                local_enabled=False,
            )
        policy = await self._policy(installed.server_default)
        default = policy.default or installed.server_default
        available = [
            OfferedModel(name=name, parameter_size=size)
            for name, size in sorted(installed.models.items())
            if policy.is_enabled(name)
        ]
        return PromoterCatalog(
            default=default,
            available=available,
            local_available=installed.local_available,
            byok=installed.byok,
        )

    async def admin_catalog(self, token: str) -> AdminCatalog:
        installed = await self._installed(token)
        policy = await self._policy(installed.server_default)
        names = set(installed.models) | {s.name for s in policy.settings}
        if policy.default:
            names.add(policy.default)
        rows = [
            AdminModelRow(
                name=name,
                parameter_size=installed.models.get(name),
                installed=name in installed.models,
                enabled=policy.is_enabled(name),
                is_default=name == policy.default,
            )
            for name in sorted(names)
        ]
        return AdminCatalog(
            models=rows,
            local_available=installed.local_available,
            server_default=installed.server_default,
            local_enabled=self._local_enabled,
        )

    async def set_enabled(
        self, token: str, name: str, enabled: bool, by: UUID
    ) -> AdminCatalog:
        """Offer a model to promoters, or withdraw it.

        Only installed models can be offered; any can be withdrawn except the
        default, which needs a successor first.
        """
        installed = await self._installed(token)
        if enabled and name not in installed.models:
            raise ModelNotInstalledError(name)
        if not enabled:
            (await self._policy(installed.server_default)).check_disable(name)
        await self._repo.set_enabled(name, enabled, by)
        return await self.admin_catalog(token)

    async def set_default(self, token: str, name: str, by: UUID) -> AdminCatalog:
        installed = await self._installed(token)
        if name not in installed.models:
            raise ModelNotInstalledError(name)
        await self._repo.set_default(name, by)
        return await self.admin_catalog(token)

