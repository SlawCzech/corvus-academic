"""Run the eval cases through an action graph and score what comes out.

    uv run python -m evals.run --model qwen3:30b-a3b
    uv run python -m evals.run --model gemma4:26b --cases pokolenie-z
    uv run python -m evals.run --model qwen3:30b-a3b --judge claude  # needs a key

The graph runs in-process — no Celery, no Postgres, no `app` — exactly as the
worker would build it for this action type. The Ollama it talks to is
OLLAMA_BASE_URL, defaulting to the host's (127.0.0.1, not "localhost": on a
Mac with the compose stack up, ::1:11434 is the container, which has no chat
models).

Each run writes ``evals/results/<timestamp>-<model>.json`` with every finding,
so a surprising number can be read back instead of re-run, and prints a
markdown table. With LANGFUSE_* set, the runs are traced and tagged ``eval``.
"""

from __future__ import annotations

import os

# Settings are read at import time, and these two are required by the service
# but unused here. Set before any `src` import.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://eval:eval@localhost/eval")
os.environ.setdefault("JWT_SECRET", "eval-" + "x" * 40)
os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
os.environ.setdefault("CHECKPOINTS_ENABLED", "false")

import argparse
import json
import time
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from src.application.graph import build_action_graph
from src.application.tasks import (
    _initial_state,  # pyright: ignore[reportPrivateUsage]
)
from src.domain.action import ActionType
from src.domain.analysis import Finding
from src.infrastructure.llm_factory import (
    ModelCredentials,
    get_llm,
)
from src.infrastructure.tracing import flush, run_config

from .dataset import EvalCase, load_cases
from .judge import Judge, llm_judge
from .metrics import CaseResult, render_markdown, score_case, summarise

RESULTS_DIR = Path(__file__).parent / "results"

_PROVIDER_KEYS = {"claude": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


def _judge_for(name: str) -> Judge:
    """A provider name judges on that provider; anything else is an Ollama tag."""
    env = _PROVIDER_KEYS.get(name)
    if env is None:
        return llm_judge(get_llm(name))
    key = os.environ.get(env, "")
    if not key:
        raise SystemExit(f"--judge {name} needs {env} in the environment")
    return llm_judge(get_llm(credentials=ModelCredentials(provider=name, api_key=key)))


def run_case(
    case: EvalCase, action_type: str, model: str, judge: Judge
) -> CaseResult:
    """Run one case through the graph and score it."""
    action_id, student_id = str(uuid.uuid4()), f"eval-{case.id}"
    state = _initial_state(
        action_id, action_type, student_id, case.context(), model, "pl"
    )
    config = run_config(
        action_type=action_type,
        action_id=action_id,
        student_id=student_id,
        model=model,
        task_id=None,
    )
    config["tags"] = [*config.get("tags", []), "eval", case.id]

    graph = build_action_graph(action_type)
    started = time.monotonic()
    done_at: dict[str, float] = {}
    final: dict[str, Any] = {}
    # "updates" says when each node finished — the parallel branches of a
    # review finish at different times, and the slowest is the one to fix.
    for mode, chunk in graph.stream(  # pyright: ignore[reportUnknownMemberType]
        state, config=config, stream_mode=["updates", "values"]
    ):
        if mode == "updates":
            for node in cast(dict[str, Any], chunk):
                done_at[node] = time.monotonic() - started
        else:
            final = cast(dict[str, Any], chunk)
    seconds = time.monotonic() - started
    flush()

    findings = cast(list[Finding], final.get("findings") or [])
    output = cast(dict[str, Any] | None, final.get("output"))
    recommendation = (
        str(output["recommendation"])
        if isinstance(output, dict) and output.get("recommendation")
        else None
    )
    return score_case(
        case,
        findings,
        judge(case, findings),
        model=model,
        seconds=seconds,
        node_seconds=done_at,
        node_errors=cast(list[str], final.get("node_errors") or []),
        error=cast(str | None, final.get("error")),
        recommendation=recommendation,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run and score the eval cases.")
    parser.add_argument("--model", required=True, help="Ollama tag under test")
    parser.add_argument(
        "--judge",
        default="qwen3:30b-a3b",
        help="Ollama tag, or 'claude' / 'openai' to judge on that provider",
    )
    parser.add_argument(
        "--action",
        default=ActionType.GENERATE_REVIEW,
        choices=[ActionType.GENERATE_REVIEW, ActionType.EVALUATE_METHODOLOGY],
    )
    parser.add_argument("--cases", nargs="*", help="case ids (default: all)")
    args = parser.parse_args(argv)

    judge = _judge_for(args.judge)
    results: list[CaseResult] = []
    for case in load_cases(args.cases):
        print(f"… {case.id} on {args.model}", flush=True)
        result = run_case(case, args.action, args.model, judge)
        print(
            f"  recall {result.recall:.2f}, {result.finding_count} findings, "
            f"{result.seconds} s",
            flush=True,
        )
        results.append(result)

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS_DIR / f"{stamp}-{args.model.replace(':', '_').replace('/', '_')}.json"
    out.write_text(
        json.dumps(
            {
                "model": args.model,
                "judge": args.judge,
                "action": args.action,
                "summary": asdict(summarise(results)),
                "cases": [asdict(r) | {"recall": r.recall} for r in results],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print()
    print(render_markdown(results))
    print(f"\nwritten to {out}")


if __name__ == "__main__":
    main()
