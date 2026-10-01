"use client"

import { useState } from "react"
import {
  SEVERITY_COLORS,
  SEVERITY_LABELS,
  SEVERITY_ORDER,
  SOURCE_LABELS,
} from "@/components/AnalysisResult"
import type { Finding, FindingSource } from "@/lib/api.types"

const SOURCE_ORDER: FindingSource[] = ["structure", "methodology", "requirements", "coherence"]

function sourceRank(finding: Finding): number {
  const rank = finding.source ? SOURCE_ORDER.indexOf(finding.source) : -1
  return rank === -1 ? SOURCE_ORDER.length : rank
}

/**
 * The paused review's findings, each with a tick the promoter can take away.
 *
 * Everything starts ticked: the analyses and the quote check already ran, and
 * the promoter's job here is to strike what they disagree with, not to build
 * the list from nothing.
 *
 * Shown the way the finished review shows them — the gravest first, and
 * within a severity one analysis after another — because the agent returns
 * them in the order its parallel analyses happened to finish. What goes back
 * is still each finding's index in that original order.
 */
export default function FindingPicker({
  findings,
  onSubmit,
}: {
  findings: Finding[]
  onSubmit: (accepted: number[]) => void
}) {
  const [kept, setKept] = useState<Set<number>>(() => new Set(findings.map((_, i) => i)))

  const groups = SEVERITY_ORDER.map((severity) => ({
    severity,
    items: findings
      .map((finding, index) => ({ finding, index }))
      .filter(({ finding }) => finding.severity === severity)
      .sort((a, b) => sourceRank(a.finding) - sourceRank(b.finding) || a.index - b.index),
  })).filter((group) => group.items.length > 0)

  function toggle(index: number) {
    setKept((current) => {
      const next = new Set(current)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return next
    })
  }

  function setGroup(indices: number[], keep: boolean) {
    setKept((current) => {
      const next = new Set(current)
      for (const index of indices) {
        if (keep) next.add(index)
        else next.delete(index)
      }
      return next
    })
  }

  return (
    <div data-testid="finding-picker">
      <p className="mb-4 text-[13px] text-muted-strong">
        Odznacz uwagi, z którymi się nie zgadzasz — recenzja powstanie tylko z
        zaznaczonych.
      </p>
      {groups.map(({ severity, items }) => {
        const indices = items.map((item) => item.index)
        const keptHere = indices.filter((index) => kept.has(index)).length
        const allKept = keptHere === indices.length
        return (
          <div key={severity} data-testid={`picker-group-${severity}`} className="mb-5">
            <div className="mb-2 flex items-center justify-between">
              <h3
                className={`inline-block rounded-md border px-2 py-0.5 text-[12px] font-semibold ${SEVERITY_COLORS[severity]}`}
              >
                {SEVERITY_LABELS[severity]} ({keptHere}/{indices.length})
              </h3>
              <button
                type="button"
                onClick={() => setGroup(indices, !allKept)}
                data-testid={`picker-group-toggle-${severity}`}
                className="text-[12px] text-muted hover:text-foreground"
              >
                {allKept ? "Odznacz wszystkie" : "Zaznacz wszystkie"}
              </button>
            </div>
            <ul className="space-y-2">
              {items.map(({ finding: f, index }) => (
                <li
                  key={index}
                  className={`rounded-lg border border-line p-3 text-[13px] ${
                    kept.has(index) ? "" : "opacity-50"
                  }`}
                >
                  <label className="flex cursor-pointer items-start gap-2.5">
                    <input
                      type="checkbox"
                      checked={kept.has(index)}
                      onChange={() => toggle(index)}
                      data-testid="finding-toggle"
                      className="mt-0.5 accent-accent"
                    />
                    <span>
                      <span className="font-semibold text-foreground">{f.section}</span>
                      {f.source && (
                        <span className="ml-2 text-[11px] text-muted">
                          {SOURCE_LABELS[f.source]}
                        </span>
                      )}
                      <span className="mt-0.5 block text-muted-strong">{f.description}</span>
                      {f.quote && (
                        <span className="mt-1.5 block border-l-2 border-line pl-2 text-[12px] text-muted">
                          „{f.quote}”
                        </span>
                      )}
                      {f.suggestion && (
                        <span className="mt-1 block italic text-muted">→ {f.suggestion}</span>
                      )}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </div>
        )
      })}
      <button
        type="button"
        onClick={() => onSubmit([...kept].sort((a, b) => a - b))}
        data-testid="resume-action"
        className="h-9 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors"
      >
        Napisz recenzję z zaznaczonych ({kept.size}/{findings.length})
      </button>
    </div>
  )
}
