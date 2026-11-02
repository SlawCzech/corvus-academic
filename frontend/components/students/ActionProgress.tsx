"use client"

import { IconCheck, IconCircleDashed } from "@tabler/icons-react"
import type { ActionProgress as Progress } from "@/lib/api.types"

// The agent reports its graph's node names; these are what a promoter reads.
// An unknown node (added on the agent side first) falls back to its own name.
const STEP_LABELS: Record<string, string> = {
  analyze_structure: "Struktura i spójność",
  analyze_methodology: "Metodologia i źródła",
  check_requirements: "Wymogi uczelni",
  digest_chapter: "Streszczenia rozdziałów",
  check_coherence: "Spójność wniosków z wynikami",
  verify: "Weryfikacja uwag",
  promoter_review: "Twój wybór uwag",
  generate_review: "Recenzja",
  propose_topic: "Propozycje tematów",
  defence_questions: "Pytania na obronę",
  check_progress: "Porównanie wersji",
  draft_meeting_note: "Szkic notatki",
  draft_student_email: "Szkic maila",
  review_fragment: "Czytanie fragmentu",
  extract_references: "Lista pozycji",
  match_references: "Dopasowanie w Crossref i katalogach",
  investigate: "Dochodzenie agenta",
  tools: "Wyszukiwania w źródłach",
  report: "Werdykty",
}

/**
 * Where a running action is: its steps, ticked off as the agent finishes
 * them. A review on a local model runs for ten minutes and more — this is the
 * difference between "working" and "stuck?".
 */
export default function ActionProgress({ progress }: { progress: Progress }) {
  const done = new Set(progress.done)
  // Not-done steps are shown alike: the review's analyses run in parallel and
  // the ones after them wait, and the agent reports only what finished.
  return (
    <ol data-testid="action-progress" className="mb-3 space-y-1">
      {progress.steps.map((step) => {
        const finished = done.has(step)
        return (
          <li
            key={step}
            data-testid="progress-step"
            data-done={finished}
            className={`flex items-center gap-2 text-[12.5px] ${finished ? "text-muted-strong" : "text-muted"}`}
          >
            {finished ? (
              <IconCheck size={14} stroke={2.5} className="text-accent" aria-label="gotowe" />
            ) : (
              <IconCircleDashed size={14} stroke={2} aria-label="czeka" />
            )}
            {STEP_LABELS[step] ?? step}
          </li>
        )
      })}
    </ol>
  )
}
