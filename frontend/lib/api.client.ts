import type { TaskStatusResponse } from "./api.types"

export async function submitAnalysis(file: File): Promise<{ task_id: string }> {
  const formData = new FormData()
  formData.append("file", file)
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
