"""Run the thesis-version retention sweep once.

`app` already sweeps daily in-process; this is for running it by hand, from
cron when the in-process loop is turned off (RETENTION_SWEEP_INTERVAL_HOURS=0),
or to see what a future date would purge:

    python scripts/purge_drafts.py
    python scripts/purge_drafts.py --now 2027-03-01T00:00:00+00:00

`--now` really purges — it moves the clock, it is not a dry run.
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime

from src.mentoring.infrastructure.retention import sweep_once


def _parse_now(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run the retention sweep once.")
    parser.add_argument(
        "--now",
        type=_parse_now,
        default=None,
        help="ISO datetime to evaluate retention at (default: the current time)",
    )
    args = parser.parse_args()
    purged = await sweep_once(args.now)
    print(f"Purged {purged} thesis version(s).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
