"use client"

import Link from "next/link"
import { useState } from "react"
import useSWR from "swr"
import { ACTION_LABELS } from "@/components/students/format"
import { cancelAction, deleteAction, fetcher } from "@/lib/api.client"
import type { ActionInProgress } from "@/lib/api.types"

/** Past this, a run is almost certainly dead — a full review takes minutes. */
const STALE_AFTER_MS = 60 * 60 * 1000

const STATUS_LABELS: Record<string, string> = {
  pending: "w kolejce",
  running: "w toku",
  awaiting_input: "czeka na Ciebie",
}

function since(iso: string, now: number): string {
  const minutes = Math.floor((now - new Date(iso).getTime()) / 60_000)
  if (minutes < 1) return "przed chwilą"
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 48) return `${hours} godz.`
  return `${Math.floor(hours / 24)} dni`
}

function startedAt(iso: string): string {
  return new Date(iso).toLocaleString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })
}

/**
 * What the dashboard's "in progress" count is made of.
 *
 * Each action has been checked with the agent before it gets here, so what
 * is listed is really going — or dead, and the promoter can clear it.
 */
export default function InProgressActions({ onChange }: { onChange: () => void }) {
  const { data, error, mutate } = useSWR<ActionInProgress[]>(
    "/api/dashboard/actions-in-progress",
    fetcher,
  )
  // One "now" per mount: ages on a list opened for a glance need not tick.
  const [now] = useState(() => Date.now())
  // Which row asks for confirmation, and of what: stopping keeps the action
  // in the student's history as "przerwana", deleting takes it out.
  const [confirm, setConfirm] = useState<{ id: string; kind: "cancel" | "delete" } | null>(
    null,
  )
  const [busyId, setBusyId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  async function apply(item: ActionInProgress, kind: "cancel" | "delete"): Promise<void> {
    setBusyId(item.id)
    setActionError(null)
    try {
      if (kind === "cancel") await cancelAction(item.student_id, item.id)
      else await deleteAction(item.student_id, item.id)
      await mutate()
      onChange()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Nie udało się")
    } finally {
      setBusyId(null)
      setConfirm(null)
    }
  }

  return (
    <div
      data-testid="in-progress-actions"
      className="mb-7 rounded-xl border border-line bg-surface p-5"
    >
      <h2 className="mb-3 text-[13px] font-semibold text-foreground">Akcje AI w toku</h2>

      {error && <p className="text-[13px] text-critical-text">Nie udało się pobrać listy.</p>}
      {data && data.length === 0 && (
        <p className="text-[13.5px] text-muted">Nic się teraz nie liczy.</p>
      )}

      {data && data.length > 0 && (
        <div className="flex flex-col">
          {data.map((item) => {
            // A review waiting for the promoter is not dead, however long it waits.
            const stale =
              item.status !== "awaiting_input" &&
              now - new Date(item.created_at).getTime() > STALE_AFTER_MS
            return (
              <div
                key={item.id}
                data-testid="in-progress-item"
                className="flex items-center justify-between gap-4 border-b border-line/60 py-2.5 text-[13.5px] last:border-none"
              >
                <span className="min-w-0">
                  <Link
                    href={`/students/${item.student_id}?section=actions`}
                    className="font-semibold text-foreground hover:text-accent"
                  >
                    {item.student_name}
                  </Link>{" "}
                  — {ACTION_LABELS[item.action_type] ?? item.action_type}
                  {" · "}
                  {STATUS_LABELS[item.status] ?? item.status}
                  <span className={`ml-2 ${stale ? "text-major-text" : "text-muted"}`}>
                    od {startedAt(item.created_at)} ({since(item.created_at, now)})
                    {stale ? " — prawdopodobnie martwa" : ""}
                  </span>
                </span>

                {confirm?.id === item.id ? (
                  <span className="flex shrink-0 items-center gap-2">
                    <span className="text-[12.5px] text-muted-strong">
                      {confirm.kind === "cancel" ? "Przerwać?" : "Usunąć z historii?"}
                    </span>
                    <button
                      type="button"
                      disabled={busyId === item.id}
                      onClick={() => void apply(item, confirm.kind)}
                      className="h-8 rounded-lg bg-critical-text px-3 text-[12.5px] font-semibold text-white disabled:opacity-50"
                    >
                      {confirm.kind === "cancel" ? "Tak, przerwij" : "Tak, usuń"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirm(null)}
                      className="h-8 rounded-lg border border-line px-3 text-[12.5px] text-foreground hover:bg-surface-alt"
                    >
                      Nie
                    </button>
                  </span>
                ) : (
                  <span className="flex shrink-0 gap-2">
                    <button
                      type="button"
                      onClick={() => setConfirm({ id: item.id, kind: "cancel" })}
                      className="h-8 rounded-lg border border-line px-3 text-[12.5px] font-medium text-critical-text hover:bg-surface-alt"
                    >
                      Przerwij
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirm({ id: item.id, kind: "delete" })}
                      className="h-8 rounded-lg border border-line px-3 text-[12.5px] font-medium text-critical-text hover:bg-surface-alt"
                    >
                      Usuń
                    </button>
                  </span>
                )}
              </div>
            )
          })}
        </div>
      )}

      {actionError && (
        <p role="alert" className="mt-2 text-[13px] text-critical-text">
          {actionError}
        </p>
      )}
    </div>
  )
}
