"use client"

import { useState } from "react"
import useSWR from "swr"
import { fetchTaskStatus, submitAnalysis } from "@/lib/api.client"
import type { AnalysisResult, TaskStatusResponse } from "@/lib/api.types"

export type AnalysisStatus = "idle" | "uploading" | "analyzing" | "done" | "error"

export interface UseAnalysisReturn {
  submit: (file: File) => Promise<void>
  status: AnalysisStatus
  result: AnalysisResult | null
  error: string | null
}

export function getRefreshInterval(data: TaskStatusResponse | undefined): number {
  if (!data) return 3000
  if (data.status === "done" || data.status === "error") return 0
  return 3000
}

export function useAnalysis(): UseAnalysisReturn {
  const [taskId, setTaskId] = useState<string | null>(null)
  const [status, setStatus] = useState<AnalysisStatus>("idle")
  const [error, setError] = useState<string | null>(null)

  const { data: pollData } = useSWR(
    taskId ? `task:${taskId}` : null,
    () => fetchTaskStatus(taskId!),
    {
      refreshInterval: getRefreshInterval,
      onSuccess(data) {
        if (data.status === "done") setStatus("done")
        else if (data.status === "error") {
          setStatus("error")
          setError(data.result?.error ?? "Analysis failed")
        }
      },
    },
  )

  const submit = async (file: File): Promise<void> => {
    setStatus("uploading")
    setError(null)
    setTaskId(null)
    try {
      const { task_id } = await submitAnalysis(file)
      setTaskId(task_id)
      setStatus("analyzing")
    } catch (err) {
      setStatus("error")
      setError(err instanceof Error ? err.message : "Upload failed")
    }
  }

  return {
    submit,
    status,
    result: pollData?.result ?? null,
    error,
  }
}
