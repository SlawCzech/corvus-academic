"use client"

import { useState } from "react"
import type { Finding, FindingSeverity } from "@/lib/api.types"

const SEVERITY_LABELS: Record<FindingSeverity, string> = {
  critical: "Krytyczna",
  major: "Istotna",
  minor: "Drobna",
}

/**
 * The paused review's findings, each with a tick the promoter can take away.
 *
 * Everything starts ticked: the analyses and the quote check already ran, and
 * the promoter's job here is to strike what they disagree with, not to build
 * the list from nothing. Indices are what goes back — the agent keeps the
 * findings in the order it returned them.
 */
export default function FindingPicker({
  findings,
  onSubmit,
}: {
  findings: Finding[]
  onSubmit: (accepted: number[]) => void
}) {
  const [kept, setKept] = useState<Set<number>>(() => new Set(findings.map((_, i) => i)))

  function toggle(index: number) {
    setKept((current) => {
      const next = new Set(current)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return next
    })
  }

  return (
    <div data-testid="finding-picker">
      <p className="mb-3 text-[13px] text-muted-strong">
        Odznacz uwagi, z którymi się nie zgadzasz — recenzja powstanie tylko z
        zaznaczonych.
      </p>
      <ul className="space-y-2">
        {findings.map((f, i) => (
          <li key={i} className="rounded-lg border border-line p-3 text-[13px]">
            <label className="flex cursor-pointer items-start gap-2.5">
              <input
                type="checkbox"
                checked={kept.has(i)}
                onChange={() => toggle(i)}
                data-testid="finding-toggle"
                className="mt-0.5 accent-accent"
              />
              <span>
                <span className="font-semibold text-foreground">{f.section}</span>
                <span className="ml-2 text-[11px] text-muted">{SEVERITY_LABELS[f.severity]}</span>
                <span className="mt-0.5 block text-muted-strong">{f.description}</span>
                {f.quote && (
                  <span className="mt-1 block border-l-2 border-line pl-2 text-[12px] text-muted">
                    „{f.quote}”
                  </span>
                )}
              </span>
            </label>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={() => onSubmit([...kept].sort((a, b) => a - b))}
        data-testid="resume-action"
        className="mt-4 h-9 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors"
      >
        Napisz recenzję z zaznaczonych ({kept.size}/{findings.length})
      </button>
    </div>
  )
}
