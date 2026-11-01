"""What one run of one case scored, computed from the judge's mapping.

Pure functions over findings and a `Judgement` — no model here, so the
arithmetic is tested like any other code and the judge stays swappable.

The numbers, and what each is for:

- **recall** — planted defects named / planted defects. The headline.
- **underrated** — named, but at a lower severity than the rules demand: a
  missing hypothesis reported as MINOR is found and still wrong.
- **duplicates** — extra findings restating a defect another finding already
  named. The review's three analyses run in parallel and cannot see each
  other; this is how often that shows.
- **false_flags** — findings asserting something the case says is untrue
  ("no conclusions" when there are conclusions). The costliest error: a
  promoter who catches one stops trusting the rest.
- **unmatched** — findings about nothing in the answer key. Not wrong by
  definition (the key is not exhaustive), but a number that climbs between
  two prompts deserves a read.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from statistics import mean

from src.domain.analysis import Finding, FindingSeverity

from .dataset import EvalCase
from .judge import Judgement

_RANK = {
    FindingSeverity.MINOR: 1,
    FindingSeverity.MAJOR: 2,
    FindingSeverity.CRITICAL: 3,
}


@dataclass
class CaseResult:
    """One case, one model, one run."""

    case_id: str
    model: str
    seconds: float
    node_seconds: dict[str, float]
    node_errors: list[str]
    error: str | None
    finding_count: int
    matched: list[str]
    missed: list[str]
    underrated: list[str]
    duplicates: int
    false_flags: list[str]
    unmatched: int
    recommendation: str | None
    recommendation_ok: bool | None
    findings: list[dict[str, str]] = field(default_factory=list[dict[str, str]])
    # Wording in the final review that tells someone what to do.
    advice: list[str] = field(default_factory=list[str])

    @property
    def recall(self) -> float:
        total = len(self.matched) + len(self.missed)
        return len(self.matched) / total if total else 1.0


def score_case(
    case: EvalCase,
    findings: Sequence[Finding],
    judgement: Judgement,
    *,
    model: str,
    seconds: float,
    node_seconds: dict[str, float],
    node_errors: list[str],
    error: str | None,
    recommendation: str | None,
    advice: Sequence[str] = (),
) -> CaseResult:
    """Turn a run and its judgement into the case's numbers."""
    matched: list[str] = []
    missed: list[str] = []
    underrated: list[str] = []
    duplicates = 0
    used: set[int] = set()

    for issue in case.expected:
        numbers = judgement.expected.get(issue.id, [])
        used.update(numbers)
        if not numbers:
            missed.append(issue.id)
            continue
        matched.append(issue.id)
        duplicates += len(numbers) - 1
        best = max(_RANK[findings[n - 1].severity] for n in numbers)
        if best < _RANK[issue.severity]:
            underrated.append(issue.id)

    false_flags: list[str] = []
    for index, claim in enumerate(case.must_not_flag, start=1):
        numbers = judgement.false_claims.get(index, [])
        used.update(numbers)
        if numbers:
            false_flags.append(claim)

    return CaseResult(
        case_id=case.id,
        model=model,
        seconds=round(seconds, 1),
        node_seconds={k: round(v, 1) for k, v in node_seconds.items()},
        node_errors=node_errors,
        error=error,
        finding_count=len(findings),
        matched=matched,
        missed=missed,
        underrated=underrated,
        duplicates=duplicates,
        false_flags=false_flags,
        unmatched=len(findings) - len(used),
        recommendation=recommendation,
        recommendation_ok=(
            recommendation in case.acceptable_recommendations
            if recommendation is not None and case.acceptable_recommendations
            else None
        ),
        advice=list(advice),
        findings=[
            {
                "severity": str(f.severity),
                "source": str(f.source or ""),
                "section": f.section,
                "description": f.description,
            }
            for f in findings
        ],
    )


@dataclass(frozen=True)
class Summary:
    """One model across every case — the line two models are compared on."""

    model: str
    cases: int
    recall: float
    underrated: int
    duplicates: int
    false_flags: int
    unmatched: int
    failed_nodes: int
    recommendations_ok: str
    seconds: float
    advice: int = 0


def summarise(results: Sequence[CaseResult]) -> Summary:
    """Aggregate a model's case results."""
    judged = [r.recommendation_ok for r in results if r.recommendation_ok is not None]
    return Summary(
        model=results[0].model if results else "",
        cases=len(results),
        recall=round(mean(r.recall for r in results), 2) if results else 0.0,
        underrated=sum(len(r.underrated) for r in results),
        duplicates=sum(r.duplicates for r in results),
        false_flags=sum(len(r.false_flags) for r in results),
        unmatched=sum(r.unmatched for r in results),
        failed_nodes=sum(len(r.node_errors) + (1 if r.error else 0) for r in results),
        recommendations_ok=f"{sum(judged)}/{len(judged)}",
        seconds=round(sum(r.seconds for r in results), 1),
        advice=sum(len(r.advice) for r in results),
    )


def render_markdown(results: Sequence[CaseResult]) -> str:
    """The report a person reads: one row per case, then the totals."""
    lines = [
        "| case | recall | missed | underrated | dup | false flags | "
        "unmatched | recommendation | failed nodes | s |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        rec = r.recommendation or "—"
        if r.recommendation_ok is not None:
            rec += " ✓" if r.recommendation_ok else " ✗"
        lines.append(
            f"| {r.case_id} | {r.recall:.2f} | {', '.join(r.missed) or '—'} | "
            f"{', '.join(r.underrated) or '—'} | {r.duplicates} | "
            f"{len(r.false_flags)} | {r.unmatched} | {rec} | "
            f"{len(r.node_errors) + (1 if r.error else 0)} | {r.seconds} |"
        )
    s = summarise(results)
    lines += [
        "",
        f"**{s.model}** — recall {s.recall:.2f} · underrated {s.underrated} · "
        f"duplicates {s.duplicates} · false flags {s.false_flags} · "
        f"unmatched {s.unmatched} · recommendations {s.recommendations_ok} · "
        f"advice in reviews {s.advice} · failed nodes {s.failed_nodes} · "
        f"{s.seconds} s",
    ]
    return "\n".join(lines)
