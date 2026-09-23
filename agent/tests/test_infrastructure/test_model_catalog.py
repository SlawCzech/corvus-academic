"""Which chat models the action panel offers."""

import httpx

from src.infrastructure.model_catalog import load_model_catalog, parse_tags


def _tag(name: str, family: str, size: str | None = None) -> dict[str, object]:
    details: dict[str, str] = {"family": family}
    if size is not None:
        details["parameter_size"] = size
    return {"name": name, "details": details}


_TAGS = {
    "models": [
        _tag("qwen3:30b-a3b", "qwen3moe", "30.5B"),
        _tag("nomic-embed-text:latest", "nomic-bert", "137M"),
        _tag("gemma4:12b", "gemma4", "11.9B"),
        _tag("mxbai-embed-large:latest", "bert"),
        {"name": "", "details": {}},
        "not-a-model",
    ]
}


def test_parse_tags_keeps_chat_models_sorted_and_drops_embeddings() -> None:
    models = parse_tags(_TAGS)

    assert [m.name for m in models] == ["gemma4:12b", "qwen3:30b-a3b"]
    assert models[1].parameter_size == "30.5B"


def test_parse_tags_tolerates_a_malformed_payload() -> None:
    assert parse_tags(None) == []
    assert parse_tags({"models": "nope"}) == []


async def test_catalog_lists_what_ollama_has_installed() -> None:
    transport = httpx.MockTransport(lambda _req: httpx.Response(200, json=_TAGS))
    async with httpx.AsyncClient(transport=transport) as client:
        catalog = await load_model_catalog(client)

    assert catalog.local_available is True
    assert [m.name for m in catalog.local] == ["gemma4:12b", "qwen3:30b-a3b"]
    assert set(catalog.byok) == {"claude", "openai"}


async def test_catalog_degrades_to_empty_when_ollama_is_down() -> None:
    def _refuse(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=req)

    async with httpx.AsyncClient(transport=httpx.MockTransport(_refuse)) as client:
        catalog = await load_model_catalog(client)

    assert catalog.local_available is False
    assert catalog.local == []
    assert catalog.default  # the server's default still stands
