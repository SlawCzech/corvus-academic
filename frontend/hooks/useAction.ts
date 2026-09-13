"use client"

import { useCallback, useState } from "react"
import useSWR, { useSWRConfig } from "swr"
import {
  acceptAction,
  fetchAction,
  triggerAction,
  type ActionOptions,
} from "@/lib/api.client"
import type { ActionType, AgentAction } from "@/lib/api.types"

const POLL_MS = 3000

/** Stop polling once the agent has finished with the action. */
export function getRefreshInterval(action: AgentAction | undefined): number {
  if (!action) return POLL_MS
  return action.status === "completed" || action.status === "failed"
    ? 0
    : POLL_MS
}

export interface UseActionReturn {
  /** The action currently being watched, refreshed while it runs. */
  action: AgentAction | null
  /** True between clicking and the agent finishing. */
  running: boolean
  error: string | null
  run: (actionType: ActionType, detail?: string, options?: ActionOptions) => Promise<void>
  accept: (topicIndex?: number) => Promise<void>
  watch: (actionId: string) => void
  dismiss: () => void
}

/**
 * Run one AI action for a student and follow it to its result.
 *
 * The same 202-then-poll shape the thesis analysis used, generalised: the
 * server refreshes the action from the agent whenever this hook asks for it,
 * so the polling stays a plain GET.
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
        if (data.status === "completed" || data.status === "failed") {
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
    watch,
    dismiss,
  }
}
