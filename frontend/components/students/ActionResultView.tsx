"use client"

import AnalysisResultView from "@/components/AnalysisResult"
import type { AgentAction, CheckedReference, ReferenceStatus } from "@/lib/api.types"

const CARD = "rounded-lg border border-line p-3 text-[13px]"

function Bullets({ title, items }: { title: string; items?: string[] }) {
  if (!items || items.length === 0) return null
  return (
    <div className="mt-3">
      <h4 className="text-[12px] font-medium uppercase tracking-wide text-muted">
        {title}
      </h4>
      <ul className="mt-1 list-disc pl-5 text-[13px] text-muted-strong">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

interface Props {
  action: AgentAction
  /**
   * Which proposed topic the promoter has selected, for propose_topic.
   * Left out, the proposals are shown to read, with nothing to pick — the
   * history and the overview, where there is no "accept" to follow.
   */
  selected?: number
  onSelect?: (index: number) => void
}

/**
 * Render whatever the action produced.
 *
 * Every action shares one envelope; what differs is the shape under
 * `output`, so this is the one place that knows the difference.
 */
const STAGE_LABELS: Record<string, string> = {
  structure: "struktura",
  methodology: "metodologia",
  requirements: "zgodność z wymogami",
  coherence: "spójność wniosków",
  digest: "streszczenia rozdziałów",
  verify: "weryfikacja uwag",
}

/**
 * The review's three analyses run in parallel; if one fails, the review is
 * still written from the other two. Say so — a thin review should not pass
 * for a clean one.
 */
function PartialAnalysisNotice({ errors }: { errors?: string[] }) {
  if (!errors || errors.length === 0) return null
  const stages = errors.map((e) => {
    const head = e.split(":")[0] ?? e
    // "digest 2.1. Metodyka: …" — one per chapter, reported as one stage.
    const stage = head.startsWith("digest") ? "digest" : head
    return STAGE_LABELS[stage] ?? stage
  })
  return (
    <p
      data-testid="partial-analysis"
      className="mb-3 rounded-lg border border-major-border bg-major-bg px-3.5 py-2.5 text-[13px] text-major-text"
    >
      Nie udała się część analizy ({stages.join(", ")}) — recenzja powstała bez
      niej. Uruchom ją ponownie, żeby mieć pełny obraz.
    </p>
  )
}

export default function ActionResultView({ action, selected, onSelect }: Props) {
  const result = action.output
  const output = result?.output

  if (action.status === "failed") {
    return (
      <p data-testid="action-error" className="text-[13px] text-critical-text">
        {action.error ?? "Akcja zakończyła się błędem."}
      </p>
    )
  }
  if (!result) return null

  switch (action.action_type) {
    case "propose_topic":
      if (onSelect === undefined) {
        return (
          <ol data-testid="topics" className="space-y-2">
            {(output?.topics ?? []).map((topic, i) => (
              <li key={i} className={CARD}>
                <p className="font-semibold text-foreground">{topic.title}</p>
                {topic.rationale && <p className="mt-1 text-muted-strong">{topic.rationale}</p>}
                {topic.scope && <p className="mt-1 text-muted">Zakres: {topic.scope}</p>}
                {topic.risks && <p className="mt-1 text-muted">Ryzyka: {topic.risks}</p>}
              </li>
            ))}
          </ol>
        )
      }
      return (
        <div data-testid="topics" className="space-y-2">
          {(output?.topics ?? []).map((topic, i) => (
            <label
              key={i}
              className={`${CARD} flex cursor-pointer gap-3 ${
                selected === i ? "border-accent" : ""
              }`}
            >
              <input
                type="radio"
                name="topic"
                checked={selected === i}
                onChange={() => onSelect(i)}
                className="mt-1 accent-accent"
              />
              <div>
                <p className="font-semibold text-foreground">{topic.title}</p>
                {topic.rationale && (
                  <p className="mt-1 text-muted-strong">{topic.rationale}</p>
                )}
                {topic.scope && (
                  <p className="mt-1 text-muted">Zakres: {topic.scope}</p>
                )}
                {topic.risks && (
                  <p className="mt-1 text-muted">Ryzyka: {topic.risks}</p>
                )}
              </div>
            </label>
          ))}
        </div>
      )

    case "defence_questions":
      return (
        <ol data-testid="questions" className="space-y-2">
          {(output?.questions ?? []).map((q, i) => (
            <li key={i} className={CARD}>
              <p className="font-semibold text-foreground">
                {i + 1}. {q.question}
              </p>
              {q.rationale && (
                <p className="mt-1 text-muted-strong">{q.rationale}</p>
              )}
              {q.section && (
                <p className="mt-1 text-[12px] text-muted">{q.section}</p>
              )}
            </li>
          ))}
        </ol>
      )

    case "check_progress":
      return (
        <div data-testid="progress">
          <p className="text-[13px] text-muted-strong">{output?.summary}</p>
          {(output?.changes ?? []).length > 0 && (
            <ul className="mt-3 space-y-2">
              {(output?.changes ?? []).map((change, i) => (
                <li key={i} className={CARD}>
                  <p className="font-semibold text-foreground">
                    {change.area}
                    {change.assessment && (
                      <span className="ml-2 text-[12px] font-normal text-muted">
                        {change.assessment}
                      </span>
                    )}
                  </p>
                  <p className="mt-1 text-muted-strong">{change.change}</p>
                </li>
              ))}
            </ul>
          )}
          <Bullets title="Wątpliwości" items={output?.concerns} />
          <Bullets title="Następne kroki" items={output?.next_steps} />
        </div>
      )

    case "verify_bibliography":
      return <BibliographyCheck references={output?.references ?? []} />

    case "draft_meeting_note":
      return (
        <div data-testid="drafted-note">
          <p className="whitespace-pre-wrap text-[13px] text-muted-strong">
            {output?.content}
          </p>
          <Bullets title="Omówione tematy" items={output?.topics_discussed} />
          <Bullets title="Ustalenia" items={output?.agreed_actions} />
        </div>
      )

    default:
      // evaluate_methodology and generate_review both speak findings/scores.
      return (
        <>
          <PartialAnalysisNotice errors={result.node_errors} />
          <AnalysisResultView result={result} />
        </>
      )
  }
}

const REFERENCE_LABELS: Record<ReferenceStatus, string> = {
  suspicious: "Podejrzana",
  mismatch: "Niezgodna z rekordem",
  not_indexed: "Nie w Crossref",
  unchecked: "Niesprawdzona",
  website: "Strona www",
  verified: "Potwierdzona",
}

const REFERENCE_STYLES: Record<ReferenceStatus, string> = {
  suspicious: "border-critical-border bg-critical-bg text-critical-text",
  mismatch: "border-major-border bg-major-bg text-major-text",
  not_indexed: "border-line text-muted-strong",
  unchecked: "border-line text-muted",
  website: "border-line text-muted",
  verified: "border-line text-muted",
}

// What needs the promoter's eyes first.
const REFERENCE_ORDER: ReferenceStatus[] = [
  "suspicious",
  "mismatch",
  "not_indexed",
  "unchecked",
  "website",
  "verified",
]

/**
 * The bibliography, grouped by what the check established. "Nie w Crossref"
 * is not an accusation — Crossref holds few Polish books — while a
 * "Podejrzana" entry claims a journal Crossref would know, and it does not.
 */
function BibliographyCheck({ references }: { references: CheckedReference[] }) {
  if (references.length === 0) {
    return <p className="text-[13px] text-muted">Nie znaleziono pozycji do sprawdzenia.</p>
  }
  return (
    <div data-testid="bibliography-check" className="space-y-4">
      <p className="text-[13px] text-muted-strong">
        {REFERENCE_ORDER.filter((s) => references.some((r) => r.status === s))
          .map((s) => `${REFERENCE_LABELS[s]}: ${references.filter((r) => r.status === s).length}`)
          .join(" · ")}
      </p>
      {REFERENCE_ORDER.map((status) => {
        const group = references.filter((r) => r.status === status)
        if (group.length === 0) return null
        return (
          <div key={status} data-testid={`references-${status}`}>
            <h4
              className={`mb-2 inline-block rounded-md border px-2 py-0.5 text-[12px] font-semibold ${REFERENCE_STYLES[status]}`}
            >
              {REFERENCE_LABELS[status]} ({group.length})
            </h4>
            <ul className="space-y-1.5">
              {group.map((r, i) => (
                <li key={i} className={CARD}>
                  <p className="text-muted-strong">{r.entry}</p>
                  {r.note && <p className="mt-1 text-[12px] text-muted">{r.note}</p>}
                  {r.doi && (
                    <a
                      href={`https://doi.org/${r.doi}`}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1 inline-block text-[12px] text-accent-hover underline"
                    >
                      doi:{r.doi}
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )
      })}
    </div>
  )
}
