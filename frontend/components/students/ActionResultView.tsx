"use client"

import AnalysisResultView from "@/components/AnalysisResult"
import type { AgentAction } from "@/lib/api.types"

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
  /** Which proposed topic the promoter has selected, for propose_topic. */
  selected: number
  onSelect: (index: number) => void
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
}

/**
 * The review's three analyses run in parallel; if one fails, the review is
 * still written from the other two. Say so — a thin review should not pass
 * for a clean one.
 */
function PartialAnalysisNotice({ errors }: { errors?: string[] }) {
  if (!errors || errors.length === 0) return null
  const stages = errors.map((e) => {
    const stage = e.split(":")[0] ?? e
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
