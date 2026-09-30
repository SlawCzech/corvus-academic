"use client"

import type {
  ActionResult,
  Finding,
  FindingSeverity,
  FindingSource,
  Score,
} from "@/lib/api.types"

const SEVERITY_ORDER: FindingSeverity[] = ["critical", "major", "minor"]

const SEVERITY_LABELS: Record<FindingSeverity, string> = {
  critical: "Krytyczne",
  major: "Poważne",
  minor: "Drobne",
}

const SOURCE_LABELS: Record<FindingSource, string> = {
  structure: "Struktura",
  methodology: "Metodologia",
  requirements: "Wymogi",
  coherence: "Spójność wniosków",
}

const SEVERITY_COLORS: Record<FindingSeverity, string> = {
  critical: "bg-critical-bg border-critical-border text-critical-text",
  major: "bg-major-bg border-major-border text-major-text",
  minor: "bg-minor-bg border-minor-border text-minor-text",
}

function FindingGroup({
  severity,
  findings,
}: {
  severity: FindingSeverity
  findings: Finding[]
}) {
  if (findings.length === 0) return null
  return (
    <div data-testid={`finding-group-${severity}`} className="mb-4">
      <h3 className={`mb-2 inline-block rounded-md border px-2 py-0.5 text-[12px] font-semibold ${SEVERITY_COLORS[severity]}`}>
        {SEVERITY_LABELS[severity]} ({findings.length})
      </h3>
      <ul className="space-y-2">
        {findings.map((f, i) => (
          <li
            key={i}
            data-testid="finding-item"
            className="rounded-lg border border-line p-3 text-[13px]"
          >
            <p className="font-semibold text-foreground">
              {f.section}
              {f.source && (
                <span
                  data-testid="finding-source"
                  className="ml-2 text-[11px] font-normal text-muted"
                >
                  {SOURCE_LABELS[f.source]}
                </span>
              )}
            </p>
            <p className="mt-0.5 text-muted-strong">{f.description}</p>
            {f.quote && (
              <blockquote
                data-testid="finding-quote"
                className="mt-1.5 border-l-2 border-line pl-2 text-[12px] text-muted"
              >
                „{f.quote}”
              </blockquote>
            )}
            {f.suggestion && (
              <p className="mt-1 italic text-muted">→ {f.suggestion}</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

function ScoreBar({ score }: { score: Score }) {
  const pct = score.max_points > 0
    ? Math.round((score.points / score.max_points) * 100)
    : 0
  return (
    <div data-testid="score-item" className="mb-3">
      <div className="mb-1 flex justify-between text-[13px] text-muted-strong">
        <span>{score.criteria}</span>
        <span>
          {score.points}/{score.max_points} ({pct}%)
        </span>
      </div>
      <div className="h-[5px] w-full rounded-full bg-surface-alt">
        <div
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          className="h-[5px] rounded-full bg-accent transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

interface AnalysisResultProps {
  result: ActionResult
}

export default function AnalysisResultView({ result }: AnalysisResultProps) {
  const findings: Finding[] = result.findings ?? []
  const scores: Score[] = result.scores ?? []
  const summary = result.summary ?? result.output?.summary ?? null
  const recommendation =
    result.recommendation ?? result.output?.recommendation ?? null

  const grouped = SEVERITY_ORDER.reduce<Record<FindingSeverity, Finding[]>>(
    (acc, sev) => {
      acc[sev] = findings.filter((f) => f.severity === sev)
      return acc
    },
    { critical: [], major: [], minor: [] },
  )

  const totalPoints = scores.reduce((sum, s) => sum + s.points, 0)
  const totalMax = scores.reduce((sum, s) => sum + s.max_points, 0)
  const totalPct = totalMax > 0 ? Math.round((totalPoints / totalMax) * 100) : 0

  return (
    <div data-testid="analysis-result">
      {scores.length > 0 && (
        <section data-testid="total-score" className="mb-6">
          <span className="block text-[11.5px] uppercase tracking-wide text-muted">
            Wynik łączny
          </span>
          <div className="mt-1 flex items-baseline gap-3">
            <span className="font-serif text-[36px] font-semibold text-foreground">
              {totalPct}%
            </span>
            <span className="text-[13px] text-muted-strong">
              {totalPoints} / {totalMax} pkt
            </span>
          </div>
          <div className="mt-2.5 h-2 w-full rounded-full bg-surface-alt">
            <div
              className="h-2 rounded-full bg-accent"
              style={{ width: `${totalPct}%` }}
            />
          </div>
        </section>
      )}

      {summary && (
        <section className="mb-6">
          <h2 className="mb-1 text-[11.5px] font-semibold uppercase tracking-wide text-muted">
            Podsumowanie
          </h2>
          <p data-testid="summary" className="text-[13.5px] text-muted-strong">
            {summary}
          </p>
        </section>
      )}

      {recommendation && (
        <section className="mb-6">
          <h2 className="mb-1 text-[11.5px] font-semibold uppercase tracking-wide text-muted">
            Rekomendacja
          </h2>
          <p data-testid="recommendation" className="text-[13.5px] text-muted-strong">
            {recommendation}
          </p>
        </section>
      )}

      {findings.length > 0 && (
        <section className="mb-6">
          <h2 className="mb-3 text-[14px] font-semibold text-foreground">Uwagi</h2>
          {SEVERITY_ORDER.map((sev) => (
            <FindingGroup key={sev} severity={sev} findings={grouped[sev]} />
          ))}
        </section>
      )}

      {scores.length > 0 && (
        <section>
          <h2 className="mb-3 text-[11.5px] font-semibold uppercase tracking-wide text-muted">
            Kryteria oceny
          </h2>
          {scores.map((s, i) => (
            <ScoreBar key={i} score={s} />
          ))}
        </section>
      )}
    </div>
  )
}
