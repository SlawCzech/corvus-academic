"""University requirements: the files, their chunks, and retrieval over them.

The documents are static data the agent owns. They are still the source of
truth on disk; the database holds them split into sections with embeddings so
an action can be given the parts that bear on the thesis in front of it
instead of the whole document.

Retrieval degrades to the file, never to nothing: an un-ingested database, a
missing embedding model or an unreachable Ollama all end with the same
requirements text every action used before this existed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import structlog

from src.domain.analysis import ThesisType
from src.infrastructure.embeddings import embed_query
from src.infrastructure.guideline_store import search_chunks
from src.infrastructure.settings import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_GUIDELINES_DIR = Path(__file__).parent / "prompts" / "guidelines"

_GUIDELINES_FILES: dict[str, str] = {
    ThesisType.BACHELOR: "university_requirements_bachelor.md",
    ThesisType.MASTER_ARTICLE: "university_requirements_master_article.md",
}

# Sections a retrieval must never drop. A normative document loses its meaning
# without the part that defines how to judge: pull three sections about
# structure and leave out the severity rules, and every finding becomes a
# guess at what "critical" means here.
_ALWAYS_INCLUDE = re.compile(r"severity|klasyfikacja|scoring", re.IGNORECASE)

_SECTION_RE = re.compile(r"^## ", re.MULTILINE)
_SUBSECTION_RE = re.compile(r"^### ", re.MULTILINE)

# A section longer than this is split into its own subsections, if it has any.
# Sized against these documents: §1 "Required Structure" is 1.5-2.7 kB and
# covers eight unrelated requirements, so retrieving it whole retrieves
# everything and the search stops meaning anything.
_MAX_CHUNK_CHARS = 900

# How much of the thesis characterises it well enough to retrieve against.
# The opening carries the topic, the research problem and the method, which is
# what the requirements are about.
_QUERY_CHARS = 2000


@dataclass(frozen=True)
class GuidelineChunk:
    """One section of a requirements document, ready to be embedded."""

    section: str
    text: str
    always_include: bool


@lru_cache(maxsize=4)
def load_guidelines(thesis_type: str) -> str:
    """Load university requirements for the given thesis type.

    Cached after first load — file is read once per process lifetime.
    Raises ValueError for unknown thesis types, FileNotFoundError if missing.
    """
    filename = _GUIDELINES_FILES.get(thesis_type)
    if filename is None:
        raise ValueError(f"No guidelines file for thesis type: {thesis_type!r}")
    path = _GUIDELINES_DIR / filename
    return path.read_text(encoding="utf-8")


def get_guidelines_path(thesis_type: str) -> Path:
    """Return the resolved path to the guidelines file (for testing)."""
    filename = _GUIDELINES_FILES.get(thesis_type)
    if filename is None:
        raise ValueError(f"No guidelines file for thesis type: {thesis_type!r}")
    return _GUIDELINES_DIR / filename


def split_into_chunks(document: str) -> list[GuidelineChunk]:
    """Split a requirements document into its numbered sections.

    Split on `##` headings rather than on a character count: these documents
    are written as numbered rules, and a rule cut in half retrieves as
    nonsense. Anything before the first heading is kept as the preamble, since
    it says which regulation the document is.
    """
    parts = _SECTION_RE.split(document)
    chunks: list[GuidelineChunk] = []

    preamble = parts[0].strip()
    if preamble:
        chunks.append(
            GuidelineChunk(
                section="0. Preamble", text=preamble, always_include=False
            )
        )

    for part in parts[1:]:
        body = part.strip()
        if not body:
            continue
        heading = body.splitlines()[0].strip()
        pinned = bool(_ALWAYS_INCLUDE.search(heading))
        chunks.extend(_section_chunks(heading, body, pinned))
    return chunks


def _section_chunks(
    heading: str, body: str, pinned: bool
) -> list[GuidelineChunk]:
    """Split one `##` section, by its `###` subsections when it is long.

    Pinned sections are never split: the severity rules are one rulebook, and
    half of it retrieved is worse than none. Every subsection keeps its parent
    heading, so a retrieved rule still says which section it belongs to.
    """
    whole = GuidelineChunk(section=heading, text=f"## {body}", always_include=pinned)
    if pinned or len(body) <= _MAX_CHUNK_CHARS:
        return [whole]

    parts = _SUBSECTION_RE.split(body)
    if len(parts) == 1:
        return [whole]

    intro = parts[0].strip()
    chunks: list[GuidelineChunk] = []
    if intro != heading:
        chunks.append(
            GuidelineChunk(section=heading, text=f"## {intro}", always_include=False)
        )
    for sub in parts[1:]:
        sub_body = sub.strip()
        if not sub_body:
            continue
        sub_heading = sub_body.splitlines()[0].strip()
        chunks.append(
            GuidelineChunk(
                section=f"{heading} / {sub_heading}",
                # The parent heading travels with the subsection: a rule
                # retrieved on its own must still be citable.
                text=f"## {heading}\n### {sub_body}",
                always_include=False,
            )
        )
    return chunks


def retrieve_relevant_guidelines(thesis_type: str, thesis_text: str) -> str:
    """Return the requirement sections that bear on this thesis.

    Falls back to the whole document when nothing has been ingested for this
    thesis type and embedding model, or when the embedding call fails.
    """
    fallback = load_guidelines(thesis_type)
    query = thesis_text.strip()[:_QUERY_CHARS]
    if not query:
        return fallback

    try:
        embedding = embed_query(query)
    except Exception as exc:
        logger.warning(
            "guideline_embedding_failed",
            thesis_type=thesis_type,
            model=settings.embedding_model,
            error=str(exc),
        )
        return fallback

    chunks = search_chunks(
        thesis_type,
        embedding,
        embedding_model=settings.embedding_model,
        limit=settings.rag_top_k,
    )
    if not chunks:
        logger.info(
            "guidelines_not_ingested_using_file",
            thesis_type=thesis_type,
            model=settings.embedding_model,
        )
        return fallback

    logger.info(
        "guidelines_retrieved",
        thesis_type=thesis_type,
        sections=[c.section for c in chunks],
    )
    return "\n\n".join(c.text for c in chunks)
