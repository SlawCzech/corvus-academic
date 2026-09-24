"use client"

import { useState } from "react"
import ActionResultView from "@/components/students/ActionResultView"
import { ACTION_LABELS } from "@/components/students/format"
import type { ActionType, AgentAction } from "@/lib/api.types"

/** Most-read first: the review is what the promoter comes back for. */
const ORDER: ActionType[] = [
  "generate_review",
  "defence_questions",
  "evaluate_methodology",
  "check_progress",
  "propose_topic",
  "draft_meeting_note",
]

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })
}

interface Latest {
  action: AgentAction
  /** A newer run of the same action is still going. */
  newerRunning: boolean
}

/**
 * The newest finished result of each action type, one row per type.
 *
 * `actions` comes newest first, as the API returns it. Older runs stay in
 * the history; this is the "what do we know about this student now" view.
 */
export function latestResults(actions: AgentAction[]): Latest[] {
  return ORDER.flatMap((type) => {
    const ofType = actions.filter((a) => a.action_type === type)
    const done = ofType.find((a) => a.status === "completed" && a.output !== null)
    if (!done) return []
    const newerRunning = ofType.some(
      (a) => (a.status === "pending" || a.status === "running") && a.created_at > done.created_at,
    )
    return [{ action: done, newerRunning }]
  })
}

interface Props {
  actions: AgentAction[]
  onShowHistory: () => void
}

export default function LatestResults({ actions, onShowHistory }: Props) {
  const [openId, setOpenId] = useState<string | null>(null)
  const latest = latestResults(actions)

  return (
    <div
      data-testid="latest-results"
      className="col-span-2 rounded-xl border border-line bg-surface"
    >
      <div className="flex items-center justify-between px-5 pt-5 pb-3">
        <h3 className="text-[11.5px] font-semibold uppercase tracking-wide text-muted">
          Wyniki AI
        </h3>
        {actions.length > 0 && (
          <button
            type="button"
            onClick={onShowHistory}
            className="text-[12.5px] text-accent hover:underline"
          >
            Cała historia →
          </button>
        )}
      </div>

      {latest.length === 0 ? (
        <p className="px-5 pb-5 text-[13.5px] italic text-muted">Nie ma jeszcze żadnych wyników.</p>
      ) : (
        <div>
          {latest.map(({ action, newerRunning }) => {
            const open = openId === action.id
            return (
              <div key={action.id} className="border-t border-line/60">
                <button
                  type="button"
                  aria-expanded={open}
                  onClick={() => setOpenId(open ? null : action.id)}
                  className="flex w-full items-center justify-between px-5 py-3 text-left text-[13.5px] text-foreground hover:bg-surface-alt"
                >
                  <span>
                    <span className="mr-1.5 inline-block w-3 text-muted">{open ? "−" : "+"}</span>
                    {ACTION_LABELS[action.action_type] ?? action.action_type}
                    {action.accepted ? " · zaakceptowana" : ""}
                  </span>
                  <span className="text-muted">
                    {newerRunning ? "nowsza w toku · " : ""}
                    {formatDate(action.created_at)}
                  </span>
                </button>
                {open && (
                  <div
                    data-testid="latest-result"
                    className="border-t border-line/60 bg-surface-alt/40 p-4"
                  >
                    <ActionResultView action={action} />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
