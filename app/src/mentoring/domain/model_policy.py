"""Which local models promoters may run actions on — the admin's allowlist.

Installing a model is a server operation (``ollama pull``); offering it is a
decision. The agent reports what is installed, this decides what is offered,
and the two meet in ``application/model_service.py``.

Until an admin has picked a default, the server's own (the agent's
``OLLAMA_MODEL``) stands in for it — a fresh install works without a visit
to the admin panel. `app` does not always know that name (only the agent
does), so ``server_default`` is optional: without it, "the default" is
simply "whatever the agent runs when asked for nothing".
"""

from dataclasses import dataclass


class ModelPolicyError(Exception):
    """An admin change that would leave promoters without a usable default."""


class ModelNotAllowedError(Exception):
    """A promoter asked for a model the admin has not made available."""


@dataclass(frozen=True)
class ModelSetting:
    """The admin's decision about one model."""

    name: str
    enabled: bool
    is_default: bool


@dataclass(frozen=True)
class ModelPolicy:
    """All of the admin's decisions about local models."""

    settings: list[ModelSetting]
    server_default: str | None = None

    @property
    def chosen_default(self) -> str | None:
        """The default the admin picked, if they have."""
        return next((s.name for s in self.settings if s.is_default), None)

    @property
    def default(self) -> str | None:
        """The model an action runs on when the promoter picks none."""
        return self.chosen_default or self.server_default

    def is_enabled(self, name: str) -> bool:
        if name == self.default:
            return True
        return any(s.name == name and s.enabled for s in self.settings)

    def resolve(self, requested: str | None) -> str | None:
        """The model to run, or None for the agent's own default.

        An empty request means the default. Anything else must be on the
        admin's list — the dropdown only offers those, but the API is not the
        dropdown.
        """
        if not requested:
            return self.chosen_default
        if not self.is_enabled(requested):
            raise ModelNotAllowedError(
                f"Model {requested!r} is not available — ask an admin to enable it"
            )
        return requested

    def check_disable(self, name: str) -> None:
        if name == self.default:
            raise ModelPolicyError(
                "Cannot disable the default model — choose another default first"
            )
