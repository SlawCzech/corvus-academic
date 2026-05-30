"use client"

import type { AnalysisResult, Finding, FindingSeverity, Score } from "@/lib/api.types"

const SEVERITY_ORDER: FindingSeverity[] = ["critical", "major", "minor"]

const SEVERITY_LABELS: Record<FindingSeverity, string> = {
  critical: "Critical",
  major: "Major",
  minor: "Minor",
}

const SEVERITY_COLORS: Record<FindingSeverity, string> = {
  critical: "bg-red-100 border-red-300 text-red-800",
  major: "bg-orange-100 border-orange-300 text-orange-800",
  minor: "bg-yellow-100 border-yellow-300 text-yellow-800",
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
      <h3 className={`mb-2 inline-block rounded px-2 py-0.5 text-sm font-semibold border ${SEVERITY_COLORS[severity]}`}>
        {SEVERITY_LABELS[severity]} ({findings.length})
      </h3>
      <ul className="space-y-2">
        {findings.map((f, i) => (
          <li
            key={i}
            data-testid="finding-item"
            className="rounded border border-gray-200 p-3 text-sm"
          >
            <p className="font-medium text-gray-800">{f.section}</p>
            <p className="mt-0.5 text-gray-600">{f.description}</p>
            {f.suggestion && (
              <p className="mt-1 text-gray-500 italic">→ {f.suggestion}</p>
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
      <div className="flex justify-between text-sm text-gray-700 mb-1">
        <span>{score.criteria}</span>
        <span>
          {score.points}/{score.max_points} ({pct}%)
        </span>
      </div>
      <div className="h-2 w-full rounded bg-gray-200">
        <div
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          className="h-2 rounded bg-blue-500 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

interface AnalysisResultProps {
  result: AnalysisResult
}

export default function AnalysisResultView({ result }: AnalysisResultProps) {
  const grouped = SEVERITY_ORDER.reduce<Record<FindingSeverity, Finding[]>>(
    (acc, sev) => {
      acc[sev] = result.findings.filter((f) => f.severity === sev)
      return acc
    },
    { critical: [], major: [], minor: [] },
  )

  return (
    <div data-testid="analysis-result">
      {result.summary && (
        <section className="mb-6">
          <h2 className="mb-1 text-base font-semibold text-gray-800">Summary</h2>
          <p data-testid="summary" className="text-sm text-gray-700">
            {result.summary}
          </p>
        </section>
      )}

      {result.recommendation && (
        <section className="mb-6">
          <h2 className="mb-1 text-base font-semibold text-gray-800">
            Recommendation
          </h2>
          <p data-testid="recommendation" className="text-sm text-gray-700">
            {result.recommendation}
          </p>
        </section>
      )}

      {result.findings.length > 0 && (
        <section className="mb-6">
          <h2 className="mb-3 text-base font-semibold text-gray-800">Findings</h2>
          {SEVERITY_ORDER.map((sev) => (
            <FindingGroup key={sev} severity={sev} findings={grouped[sev]} />
          ))}
        </section>
      )}

      {result.scores.length > 0 && (
        <section>
          <h2 className="mb-3 text-base font-semibold text-gray-800">Scores</h2>
          {result.scores.map((s, i) => (
            <ScoreBar key={i} score={s} />
          ))}
        </section>
      )}
    </div>
  )
}
