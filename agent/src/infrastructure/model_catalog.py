"""Which chat models a promoter can actually pick.

The action panel used to take a free-text Ollama tag — fine for whoever set
up the server, a guessing game for everyone else. This asks the Ollama the
worker talks to what it has installed, so the choice is made from a list.
"""

from dataclasses import dataclass
from typing import cast

import httpx
import structlog

from src.infrastructure.llm_factory import byok_models
from src.infrastructure.settings import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_TIMEOUT = 5.0


@dataclass(frozen=True)
class LocalModel:
    name: str
    parameter_size: str | None


@dataclass(frozen=True)
class ModelCatalog:
    backend: str
    default: str
    local: list[LocalModel]
    """False when Ollama did not answer — the list is empty, not "none installed"."""
    local_available: bool
    byok: dict[str, str]


def _is_embedding(name: str, family: str) -> bool:
    # Embedding models sit in the same Ollama and answer /api/tags alike, but
    # a chat request to one fails. Ollama marks them only by family.
    return "embed" in name or family.endswith("bert")


def _as_dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def parse_tags(payload: object) -> list[LocalModel]:
    """Chat models from an Ollama ``/api/tags`` response, sorted by name."""
    raw = _as_dict(payload).get("models")
    items = cast(list[object], raw) if isinstance(raw, list) else []
    models: list[LocalModel] = []
    for item in items:
        entry = _as_dict(item)
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            continue
        details = _as_dict(entry.get("details"))
        family = details.get("family")
        size = details.get("parameter_size")
        if _is_embedding(name, family if isinstance(family, str) else ""):
            continue
        parameter_size = size if isinstance(size, str) else None
        models.append(LocalModel(name=name, parameter_size=parameter_size))
    return sorted(models, key=lambda m: m.name)


async def load_model_catalog(client: httpx.AsyncClient) -> ModelCatalog:
    """Ask Ollama for its chat models; degrade to an empty list if it is down."""
    local: list[LocalModel] = []
    available = False
    try:
        response = await client.get(
            f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=_TIMEOUT
        )
        response.raise_for_status()
        local = parse_tags(response.json())
        available = True
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("ollama_tags_unavailable", error=str(exc))

    return ModelCatalog(
        backend=settings.model_backend,
        default=settings.ollama_model,
        local=local,
        local_available=available,
        byok=byok_models(),
    )
