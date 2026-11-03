"""Extraction in a child process: same result, and limits that hold."""

import sys
import time
from multiprocessing.connection import Connection

import pytest

from src.document.isolated import _run, extract_isolated  # pyright: ignore[reportPrivateUsage]

_GB = 1024 * 1024 * 1024


async def test_a_pdf_reads_the_same_as_in_process(pdf_bytes: bytes) -> None:
    document = await extract_isolated(
        pdf_bytes, "praca.pdf", timeout_seconds=60, max_bytes=_GB
    )

    assert document.format == "pdf"
    assert document.pages == 1
    assert "Chapter 1" in document.text


async def test_a_docx_reads_the_same_as_in_process(docx_bytes: bytes) -> None:
    document = await extract_isolated(
        docx_bytes, "praca.docx", timeout_seconds=60, max_bytes=_GB
    )

    assert document.format == "docx"
    assert "This is a test thesis document." in document.text


async def test_an_unreadable_file_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="Unsupported format"):
        await extract_isolated(b"hello", "notes.txt", timeout_seconds=60, max_bytes=_GB)


def _hangs(conn: Connection, data: bytes, name: str, ctype: str, limit: int) -> None:
    time.sleep(60)


def _dies(conn: Connection, data: bytes, name: str, ctype: str, limit: int) -> None:
    sys.exit(1)


def _hoards(conn: Connection, data: bytes, name: str, ctype: str, limit: int) -> None:
    from src.document.isolated import _limit_memory  # pyright: ignore[reportPrivateUsage]

    _limit_memory(limit)
    hoard = bytearray(4 * limit)
    conn.send(("ok", str(len(hoard)), 1, "pdf"))


def test_a_child_past_its_time_is_killed() -> None:
    started = time.monotonic()
    reply = _run(b"", "x.pdf", "", 1, _GB, target=_hangs)

    assert reply == ("invalid", "File took too long to read")
    assert time.monotonic() - started < 10


def test_a_child_that_dies_without_answering_is_refused() -> None:
    assert _run(b"", "x.pdf", "", 30, _GB, target=_dies) == (
        "invalid",
        "File could not be read",
    )


@pytest.mark.skipif(
    sys.platform != "linux", reason="RLIMIT_AS is enforced on Linux only"
)
def test_a_child_past_its_memory_is_refused() -> None:
    reply = _run(b"", "x.pdf", "", 30, 256 * 1024 * 1024, target=_hoards)
    assert reply[0] == "invalid"
