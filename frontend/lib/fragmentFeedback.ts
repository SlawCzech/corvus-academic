import type {
  ActionResult,
  FragmentReview,
  FragmentVerdict,
  PartState,
} from "@/lib/api.types"

export const VERDICT_LABELS: Record<FragmentVerdict, string> = {
  on_track: "Na razie OK",
  needs_changes: "Do poprawy",
  needs_additions: "Do uzupełnienia",
}

export const PART_STATE_LABELS: Record<PartState, string> = {
  ...VERDICT_LABELS,
  not_submitted: "Nieoddana",
  awaiting_feedback: "Czeka na Ciebie",
}

export const PART_STATE_STYLES: Record<PartState, string> = {
  on_track: "bg-success-bg text-success-text",
  needs_changes: "bg-major-bg text-major-text",
  needs_additions: "bg-major-bg text-major-text",
  awaiting_feedback: "bg-accent-soft text-accent-hover",
  not_submitted: "bg-surface-alt text-muted-strong",
}

/** The agent's reply to `review_fragment`, unwrapped; null while there is none. */
export function fragmentReview(result: ActionResult | null): FragmentReview | null {
  const output = result?.output as unknown as FragmentReview | undefined
  return output?.direction ? output : null
}

function section(title: string, items: string[]): string | null {
  if (items.length === 0) return null
  return `${title}:\n${items.map((item) => `- ${item}`).join("\n")}`
}

/**
 * The draft as editable text — what the promoter turns into their own words.
 * The summary stays out: it is a note for the promoter, and the student knows
 * what they handed in.
 */
export function fragmentFeedbackDraft(review: FragmentReview): string {
  const parts = [
    review.answer || null,
    section("Co działa", review.strengths),
    section("Co już poprawione", review.addressed),
    section(
      "Do zmiany",
      review.changes.map((c) => c.point),
    ),
    section("Do dodania", review.additions),
    review.next_step ? `Następny krok: ${review.next_step}` : null,
  ]
  return parts.filter((part) => part !== null).join("\n\n")
}
