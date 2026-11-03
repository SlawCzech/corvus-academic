"""Text extraction in a child process, with a time and a memory limit.

An uploaded file is untrusted: a crafted PDF can make the parser spin or
allocate without end. In `app`'s own process that would freeze every request
(extraction is synchronous) or take the service down. In a child, the worst
it can do is be killed, and the upload is refused like any unreadable file.

The child is spawned, not forked: a fork of a process running an event loop
and a database pool inherits both, and neither survives it.
"""

import asyncio
import multiprocessing
from collections.abc import Callable
from multiprocessing.connection import Connection
from multiprocessing.context import SpawnProcess

import structlog

from src.document.document import Document
from src.document.extractor import extract
from src.shared.settings import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_CONTEXT = multiprocessing.get_context("spawn")
# What the parent waits for after a kill before it gives up on the child.
_REAP_SECONDS = 5.0

_Reply = tuple[str, str, int, str] | tuple[str, str]


def _limit_memory(max_bytes: int) -> None:
    """Cap the child's address space, where the platform allows it.

    Linux (the server) enforces RLIMIT_AS; macOS refuses to set it, and the
    time limit is then the only guard — acceptable on a developer machine.
    """
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
    except (ImportError, ValueError, OSError):
        pass


def _child(
    conn: Connection, data: bytes, filename: str, content_type: str, max_bytes: int
) -> None:
    """Entry point of the child: extract, send the result back, exit."""
    _limit_memory(max_bytes)
    reply: _Reply
    try:
        document = extract(data, filename, content_type)
        reply = ("ok", document.text, document.pages, document.format)
    except ValueError as exc:
        reply = ("invalid", str(exc))
    except MemoryError:
        reply = ("invalid", "File needs more memory to read than is allowed")
    except Exception as exc:  # noqa: BLE001 — anything else is an unreadable file
        reply = ("invalid", f"File could not be read: {type(exc).__name__}")
    conn.send(reply)
    conn.close()


def _run(
    data: bytes,
    filename: str,
    content_type: str,
    timeout_seconds: float,
    max_bytes: int,
    target: Callable[[Connection, bytes, str, str, int], None] = _child,
) -> _Reply:
    """Run one extraction in a fresh child and wait for it — blocking.

    ``target`` is the child's entry point; tests swap it for one that hangs
    or dies, which a monkeypatch could not reach across a spawn.
    """
    receiver, sender = _CONTEXT.Pipe(duplex=False)
    process: SpawnProcess = _CONTEXT.Process(
        target=target,
        args=(sender, data, filename, content_type, max_bytes),
        daemon=True,
    )
    process.start()
    sender.close()
    try:
        if receiver.poll(timeout_seconds):
            try:
                return receiver.recv()
            except EOFError:
                pass  # died before answering — killed by the memory limit
            return ("invalid", "File could not be read")
        logger.warning("extraction_timed_out", filename=filename)
        return ("invalid", "File took too long to read")
    finally:
        receiver.close()
        if process.is_alive():
            process.kill()
        process.join(_REAP_SECONDS)


async def extract_isolated(
    data: bytes,
    filename: str,
    content_type: str = "",
    *,
    timeout_seconds: float,
    max_bytes: int,
) -> Document:
    """Extract text as ``extract`` does, but in a child process with limits.

    Raises ValueError for an unsupported or unreadable file, for one that
    takes longer than ``timeout_seconds`` and for one that needs more than
    ``max_bytes`` of memory — callers already answer those with a 422.
    """
    reply = await asyncio.to_thread(
        _run, data, filename, content_type, timeout_seconds, max_bytes
    )
    match reply:
        case ("ok", text, pages, fmt):
            return Document(text=text, pages=pages, format=fmt)
        case (_, message, *_):
            raise ValueError(message)


async def extract_upload(
    data: bytes, filename: str, content_type: str = ""
) -> Document:
    """Extract an upload's text the way the settings say: isolated, or not.

    Either way off the event loop, so a long file never stalls other requests.
    Raises ValueError for an unsupported, unreadable or too costly file.
    """
    if not settings.extraction_isolated:
        return await asyncio.to_thread(extract, data, filename, content_type)
    return await extract_isolated(
        data,
        filename,
        content_type,
        timeout_seconds=settings.extraction_timeout_seconds,
        max_bytes=settings.extraction_max_memory_bytes,
    )
