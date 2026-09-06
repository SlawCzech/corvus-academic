"use client"

import AnalysisResultView from "@/components/AnalysisResult"
import type { AgentAction } from "@/lib/api.types"

const CARD =
  "rounded-lg border border-gray-200 dark:border-gray-800 p-3 text-[13px]"

function Bullets({ title, items }: { title: string; items?: string[] }) {
  if (!items || items.length === 0) return null
  return (
    <div className="mt-3">
      <h4 className="text-[12px] font-medium uppercase tracking-wide text-gray-400">
        {title}
      </h4>
      <ul className="mt-1 list-disc pl-5 text-[13px] text-gray-700 dark:text-gray-300">
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
export default function ActionResultView({ action, selected, onSelect }: Props) {
  const result = action.output
  const output = result?.output

  if (action.status === "failed") {
    return (
      <p data-testid="action-error" className="text-[13px] text-red-600">
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
                selected === i ? "border-gray-900 dark:border-gray-300" : ""
              }`}
            >
              <input
                type="radio"
                name="topic"
                checked={selected === i}
                onChange={() => onSelect(i)}
                className="mt-1 accent-gray-900 dark:accent-white"
              />
              <div>
                <p className="font-medium text-gray-900 dark:text-gray-100">
                  {topic.title}
                </p>
                {topic.rationale && (
                  <p className="mt-1 text-gray-600 dark:text-gray-400">
                    {topic.rationale}
                  </p>
                )}
                {topic.scope && (
                  <p className="mt-1 text-gray-500">Zakres: {topic.scope}</p>
                )}
                {topic.risks && (
                  <p className="mt-1 text-gray-500">Ryzyka: {topic.risks}</p>
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
              <p className="font-medium text-gray-900 dark:text-gray-100">
                {i + 1}. {q.question}
              </p>
              {q.rationale && (
                <p className="mt-1 text-gray-600 dark:text-gray-400">
                  {q.rationale}
                </p>
              )}
              {q.section && (
                <p className="mt-1 text-[12px] text-gray-400">{q.section}</p>
              )}
            </li>
          ))}
        </ol>
      )

    case "check_progress":
      return (
        <div data-testid="progress">
          <p className="text-[13px] text-gray-700 dark:text-gray-300">
            {output?.summary}
          </p>
          {(output?.changes ?? []).length > 0 && (
            <ul className="mt-3 space-y-2">
              {(output?.changes ?? []).map((change, i) => (
                <li key={i} className={CARD}>
                  <p className="font-medium text-gray-900 dark:text-gray-100">
                    {change.area}
                    {change.assessment && (
                      <span className="ml-2 text-[12px] font-normal text-gray-400">
                        {change.assessment}
                      </span>
                    )}
                  </p>
                  <p className="mt-1 text-gray-600 dark:text-gray-400">
                    {change.change}
                  </p>
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
          <p className="whitespace-pre-wrap text-[13px] text-gray-700 dark:text-gray-300">
            {output?.content}
          </p>
          <Bullets title="Omówione tematy" items={output?.topics_discussed} />
          <Bullets title="Ustalenia" items={output?.agreed_actions} />
        </div>
      )

    default:
      // evaluate_methodology and generate_review both speak findings/scores.
      return <AnalysisResultView result={result} />
  }
}
