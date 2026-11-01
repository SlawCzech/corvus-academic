import type { StudentStatus } from "@/lib/api.types"

export const ACTION_LABELS: Record<string, string> = {
  propose_topic: "Propozycja tematu",
  defence_questions: "Pytania na obronę",
  check_progress: "Sprawdzenie postępu",
  evaluate_methodology: "Ocena metodologii",
  draft_meeting_note: "Szkic notatki",
  generate_review: "Recenzja finalna",
  trial_review: "Recenzja próbna",
  verify_bibliography: "Sprawdzenie bibliografii",
  review_fragment: "Feedback do fragmentu",
}

export const STUDENT_STATUS_LABELS: Record<StudentStatus, string> = {
  active: "Aktywny",
  graduated: "Obroniony",
  archived: "Archiwalny",
}

export const STUDENT_STATUS_STYLES: Record<StudentStatus, string> = {
  active: "bg-success-bg text-success-text",
  graduated: "bg-info-bg text-info-text",
  archived: "bg-surface-alt text-muted-strong",
}

export function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const hours = Math.floor(diffMs / 3_600_000)
  if (hours < 1) return "przed chwilą"
  if (hours < 24) return `${hours} godz. temu`
  const days = Math.floor(hours / 24)
  if (days < 14) return `${days} dni temu`
  return new Date(iso).toLocaleDateString("pl-PL")
}
