"""Embedding model access.

Kept separate from `llm_factory` because it answers a different question:
not "which model writes the review" but "which model turns text into vectors
we can compare". They can be different models, and the embedding one must
stay fixed for as long as the stored vectors do.
"""

from collections.abc import Sequence

from langchain_ollama import OllamaEmbeddings

from src.infrastructure.settings import settings


def get_embedder() -> OllamaEmbeddings:
    """Return the embedding model named by settings.

    Self-hosted only: embeddings are computed over the university's
    requirements and over the student's thesis, which is exactly the material
    the local-first default exists to keep local. A user's own provider key
    pays for the review, not for indexing someone's unpublished thesis.
    """
    return OllamaEmbeddings(
        model=settings.embedding_model,
        base_url=settings.ollama_base_url,
    )


def embed_query(text: str) -> list[float]:
    """Embed one piece of text for a similarity search."""
    return get_embedder().embed_query(text)


def embed_documents(texts: Sequence[str]) -> list[list[float]]:
    """Embed a batch of chunks for storage."""
    return get_embedder().embed_documents(list(texts))
