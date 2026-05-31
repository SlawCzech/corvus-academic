import type { TaskStatusResponse } from "./api.types"

export interface AnalysisOptions {
  model: string
  mode: string
}

export async function submitAnalysis(
  file: File,
  options: AnalysisOptions,
): Promise<{ task_id: string }> {
  const formData = new FormData()
  formData.append("file", file)
  formData.append("model", options.model)
  formData.append("mode", options.mode)
  const res = await fetch("/api/analyze", { method: "POST", body: formData })
  if (!res.ok) {
    const msg = await res.text()
    throw new Error(`Upload failed (${res.status}): ${msg}`)
  }
  return res.json() as Promise<{ task_id: string }>
}

export async function fetchTaskStatus(
  taskId: string,
): Promise<TaskStatusResponse> {
  const res = await fetch(`/api/status/${taskId}`)
  if (!res.ok) throw new Error(`Status check failed: ${res.status}`)
  return res.json() as Promise<TaskStatusResponse>
}
