"use client"

import { useState } from "react"
import ActionResultView from "@/components/students/ActionResultView"
import { useAction } from "@/hooks/useAction"
import type { ActionType, Student } from "@/lib/api.types"

interface ActionSpec {
  type: ActionType
  label: string
  hint: string
  /** What the promoter types before running it, if anything. */
  detailLabel?: string
  /** True when accepting writes something back to the student's record. */
  acceptable?: boolean
  acceptLabel?: string
}

const ACTIONS: ActionSpec[] = [
  {
    type: "propose_topic",
    label: "Zaproponuj temat",
    hint: "Trzy propozycje na podstawie kierunku i notatek",
    detailLabel: "Wskazówki dla modelu (opcjonalnie)",
    acceptable: true,
    acceptLabel: "Ustaw jako temat pracy",
  },
  {
    type: "defence_questions",
    label: "Pytania na obronę",
    hint: "Trzy pytania z ostatniej wersji pracy",
    detailLabel: "Na co zwrócić uwagę (opcjonalnie)",
  },
  {
    type: "check_progress",
    label: "Sprawdź postęp",
    hint: "Porównanie dwóch ostatnich wersji",
  },
  {
    type: "evaluate_methodology",
    label: "Oceń metodologię",
    hint: "Uwagi do metody i bibliografii",
  },
  {
    type: "draft_meeting_note",
    label: "Spisz notatkę",
    hint: "Notatka ze spotkania z twoich skrótów",
    detailLabel: "Skrócone punkty ze spotkania",
    acceptable: true,
    acceptLabel: "Zapisz jako notatkę",
  },
  {
    type: "generate_review",
    label: "Napisz recenzję",
    hint: "Pełna recenzja ostatniej wersji",
  },
]

const STATUS_LABELS: Record<string, string> = {
  pending: "W kolejce",
  running: "Liczy się…",
  completed: "Gotowe",
  failed: "Błąd",
}

export default function ActionPanel({ student }: { student: Student }) {
  const { action, running, error, run, accept, dismiss } = useAction(student.id)
  const [selectedType, setSelectedType] = useState<ActionType | null>(null)
  const [detail, setDetail] = useState("")
  const [topicIndex, setTopicIndex] = useState(0)

  const spec = ACTIONS.find((a) => a.type === selectedType) ?? null
  const shown = action && action.action_type === selectedType ? action : null
  const canAccept =
    shown?.status === "completed" && !shown.accepted && spec?.acceptable

  async function start(): Promise<void> {
    if (!selectedType) return
    setTopicIndex(0)
    await run(selectedType, detail.trim() || undefined)
  }

  return (
    <section className="mb-10">
      <h2 className="mb-3 text-[15px] font-semibold text-gray-900 dark:text-gray-100">
        Akcje AI
      </h2>

      <div className="flex flex-wrap gap-2">
        {ACTIONS.map((a) => (
          <button
            key={a.type}
            type="button"
            title={a.hint}
            onClick={() => {
              setSelectedType(a.type)
              setDetail("")
              dismiss()
            }}
            className={`h-8 rounded-md border px-3 text-[13px] transition-colors ${
              selectedType === a.type
                ? "border-gray-900 dark:border-gray-300 text-gray-900 dark:text-gray-100"
                : "border-gray-200 dark:border-gray-800 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
            }`}
          >
            {a.label}
          </button>
        ))}
      </div>

      {spec && (
        <div className="mt-4 rounded-lg border border-gray-200 dark:border-gray-800 p-4">
          <p className="text-[13px] text-gray-500">{spec.hint}</p>

          {spec.detailLabel && (
            <label className="mt-3 block">
              <span className="mb-1 block text-[12px] text-gray-500">
                {spec.detailLabel}
              </span>
              <textarea
                value={detail}
                onChange={(e) => setDetail(e.target.value)}
                rows={3}
                className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-[14px] text-gray-900 dark:text-gray-100 focus:border-gray-900 dark:focus:border-gray-300 focus:outline-none"
              />
            </label>
          )}

          <button
            type="button"
            onClick={() => void start()}
            disabled={running}
            data-testid="run-action"
            className="mt-3 h-8 rounded-md bg-gray-900 dark:bg-white px-4 text-[13px] font-medium text-white dark:text-gray-900 disabled:opacity-50"
          >
            {running ? "Pracuje…" : "Uruchom"}
          </button>

          {shown && (
            <div className="mt-4 border-t border-gray-100 dark:border-gray-900 pt-4">
              <p
                data-testid="action-status"
                className="mb-3 text-[12px] uppercase tracking-wide text-gray-400"
              >
                {STATUS_LABELS[shown.status] ?? shown.status}
              </p>

              <ActionResultView
                action={shown}
                selected={topicIndex}
                onSelect={setTopicIndex}
              />

              {canAccept && (
                <button
                  type="button"
                  onClick={() => void accept(topicIndex)}
                  data-testid="accept-action"
                  className="mt-4 h-8 rounded-md border border-gray-900 dark:border-gray-300 px-4 text-[13px] font-medium text-gray-900 dark:text-gray-100"
                >
                  {spec.acceptLabel ?? "Zaakceptuj"}
                </button>
              )}

              {shown.accepted && (
                <p className="mt-3 text-[13px] text-gray-500">
                  Zaakceptowano.
                </p>
              )}
            </div>
          )}

          {error && (
            <p data-testid="action-panel-error" className="mt-3 text-[13px] text-red-600">
              {error}
            </p>
          )}
        </div>
      )}
    </section>
  )
}
