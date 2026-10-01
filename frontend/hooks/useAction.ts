"use client"

import { useCallback, useState } from "react"
import useSWR, { useSWRConfig } from "swr"
import {
  acceptAction,
  cancelAction,
  fetchAction,
  resumeAction,
  triggerAction,
  type ActionOptions,
} from "@/lib/api.client"
import type { ActionType, AgentAction } from "@/lib/api.types"

const POLL_MS = 3000

function isFinished(action: AgentAction): boolean {
  return action.status === "completed" || action.status === "failed" || action.status === "cancelled"
}

/** Still the promoter's business: queued, running, or waiting for their answer. */
export function isUnfinished(action: AgentAction): boolean {
  return (
    action.status === "pending" ||
    action.status === "running" ||
    action.status === "awaiting_input"
  )
}

/**
 * Stop polling once the agent has finished with the action — or was stopped,
 * or is waiting for the promoter: nothing changes until they answer.
 */
export function getRefreshInterval(action: AgentAction | undefined): number {
  if (!action) return POLL_MS
  return isFinished(action) || action.status === "awaiting_input" ? 0 : POLL_MS
}

export interface UseActionReturn {
  /** The action currently being watched, refreshed while it runs. */
  action: AgentAction | null
  /** True between clicking and the agent finishing. */
  running: boolean
  error: string | null
  run: (actionType: ActionType, detail?: string, options?: ActionOptions) => Promise<void>
  accept: (topicIndex?: number) => Promise<void>
  /** Stop the watched action — a wrong request, or one that runs forever. */
  cancel: () => Promise<void>
  /** Continue a paused review with the findings the promoter kept. */
  resume: (acceptedFindings: number[]) => Promise<void>
  watch: (actionId: string) => void
  dismiss: () => void
}

/**
 * Run one AI action for a student and follow it to its result.
 *
 * The same 202-then-poll shape the thesis analysis used, generalised: the
 * server refreshes the action from the agent whenever this hook asks for it,
 * so the polling stays a plain GET.
 *
 * `watch` picks up an action started earlier — the promoter left the page
 * while a review was running and came back to it.
 */
export function useAction(studentId: string): UseActionReturn {
  const [actionId, setActionId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { mutate } = useSWRConfig()

  const { data: action } = useSWR<AgentAction>(
    actionId ? `action:${studentId}:${actionId}` : null,
    () => fetchAction(studentId, actionId!),
    {
      refreshInterval: getRefreshInterval,
      onSuccess(data) {
        if (data.status === "failed") {
          setError(data.error ?? "Akcja zakończyła się błędem")
        }
        if (isFinished(data)) {
          void mutate(`/api/students/${studentId}/actions`)
        }
      },
    },
  )

  const run = useCallback(
    async (actionType: ActionType, detail?: string, options?: ActionOptions) => {
      setError(null)
      setActionId(null)
      try {
        const started = await triggerAction(studentId, actionType, detail, options)
        setActionId(started.id)
        void mutate(`/api/students/${studentId}/actions`)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Nie udało się uruchomić akcji")
      }
    },
    [studentId, mutate],
  )

  const accept = useCallback(
    async (topicIndex = 0) => {
      if (!actionId) return
      setError(null)
      try {
        await acceptAction(studentId, actionId, topicIndex)
        void mutate(`action:${studentId}:${actionId}`)
        void mutate(`/api/students/${studentId}/actions`)
        void mutate(`/api/students/${studentId}`)
        void mutate(`/api/students/${studentId}/meeting-notes`)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Nie udało się zaakceptować")
      }
    },
    [studentId, actionId, mutate],
  )

  const cancel = useCallback(async () => {
    if (!actionId) return
    setError(null)
    try {
      const stopped = await cancelAction(studentId, actionId)
      void mutate(`action:${studentId}:${actionId}`, stopped, { revalidate: false })
      void mutate(`/api/students/${studentId}/actions`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się przerwać akcji")
    }
  }, [studentId, actionId, mutate])

  const resume = useCallback(
    async (acceptedFindings: number[]) => {
      if (!actionId) return
      setError(null)
      try {
        const resumed = await resumeAction(studentId, actionId, acceptedFindings)
        // Pending again: the refresh interval picks polling back up.
        void mutate(`action:${studentId}:${actionId}`, resumed, { revalidate: false })
      } catch (err) {
        setError(err instanceof Error ? err.message : "Nie udało się wznowić recenzji")
      }
    },
    [studentId, actionId, mutate],
  )

  const watch = useCallback((id: string) => {
    setError(null)
    setActionId(id)
  }, [])

  const dismiss = useCallback(() => {
    setActionId(null)
    setError(null)
  }, [])

  const running =
    action != null && (action.status === "pending" || action.status === "running")

  return {
    action: action ?? null,
    running,
    error,
    run,
    accept,
    cancel,
    resume,
    watch,
    dismiss,
  }
}
