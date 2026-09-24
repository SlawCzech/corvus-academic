"use client"

import { useState } from "react"
import { useSWRConfig } from "swr"
import { IconChevronDown } from "@tabler/icons-react"
import ModelSelect, { useAvailableModel } from "@/components/ai/ModelSelect"
import ReviewToneChoice from "@/components/ai/ReviewToneChoice"
import ActionResultView from "@/components/students/ActionResultView"
import GuidelinePicker from "@/components/students/GuidelinePicker"
import { useAction } from "@/hooks/useAction"
import { useAiDefaults, type AiDefaults } from "@/lib/aiDefaults"
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
  cancelled: "Przerwano",
}

/** Judged against university requirements — the chosen set matters here. */
const USES_GUIDELINES: ActionType[] = ["generate_review", "evaluate_methodology"]

const optionInputClass =
  "w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[13.5px] " +
  "text-foreground focus:border-accent focus:outline-none"

export default function ActionPanel({ student }: { student: Student }) {
  const defaults = useAiDefaults()
  // Remounts once the real (possibly non-fallback) defaults are known, so the
  // panel's local option state starts from them without an effect.
  return (
    <ActionPanelInner
      key={`${defaults.model}:${defaults.language}:${defaults.reviewTone}`}
      student={student}
      defaults={defaults}
    />
  )
}

function ActionPanelInner({
  student,
  defaults,
}: {
  student: Student
  defaults: AiDefaults
}) {
  const { action, running, error, run, accept, cancel, dismiss } = useAction(student.id)
  const { mutate } = useSWRConfig()
  const [selectedType, setSelectedType] = useState<ActionType | null>(null)
  const [detail, setDetail] = useState("")
  const [topicIndex, setTopicIndex] = useState(0)

  const [optionsOpen, setOptionsOpen] = useState(false)
  const [model, setModel] = useState(defaults.model)
  const [language, setLanguage] = useState(defaults.language)
  const [reviewTone, setReviewTone] = useState(defaults.reviewTone)
  // What actually gets sent: a saved model the admin has since withdrawn
  // falls back to the default rather than getting the action refused.
  const { effective: effectiveModel, withdrawn } = useAvailableModel(model)

  const spec = ACTIONS.find((a) => a.type === selectedType) ?? null
  const shown = action && action.action_type === selectedType ? action : null
  const canAccept =
    shown?.status === "completed" && !shown.accepted && spec?.acceptable
  const showTone = selectedType === "generate_review"
  const showGuidelines = selectedType !== null && USES_GUIDELINES.includes(selectedType)

  async function start(): Promise<void> {
    if (!selectedType) return
    setTopicIndex(0)
    await run(selectedType, detail.trim() || undefined, {
      model: effectiveModel || undefined,
      language,
      reviewTone,
    })
  }

  return (
    <section>
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
            className={`h-9 rounded-lg border px-3.5 text-[13px] font-medium transition-colors ${
              selectedType === a.type
                ? "border-accent bg-accent-soft text-accent-hover"
                : "border-line text-muted-strong hover:text-foreground"
            }`}
          >
            {a.label}
          </button>
        ))}
      </div>

      {spec && (
        <div className="mt-4 rounded-xl border border-line bg-surface p-5">
          <p className="text-[13.5px] text-muted-strong">{spec.hint}</p>

          {spec.detailLabel && (
            <label className="mt-3.5 block">
              <span className="mb-1 block text-[12px] text-muted">
                {spec.detailLabel}
              </span>
              <textarea
                value={detail}
                onChange={(e) => setDetail(e.target.value)}
                rows={3}
                className="w-full rounded-lg border border-line bg-surface px-3.5 py-2 text-[14px] text-foreground focus:border-accent focus:outline-none"
              />
            </label>
          )}

          {showGuidelines && (
            <div className="mt-3.5">
              <GuidelinePicker
                student={student}
                onChange={(next) =>
                  void mutate(`/api/students/${student.id}`, next, { revalidate: false })
                }
              />
            </div>
          )}

          {showTone && (
            <div className="mt-3.5">
              <ReviewToneChoice
                name="action-review-tone"
                value={reviewTone}
                onChange={setReviewTone}
              />
            </div>
          )}

          <button
            type="button"
            onClick={() => setOptionsOpen((v) => !v)}
            className="mt-3.5 flex items-center gap-1 text-[12.5px] text-muted hover:text-foreground"
          >
            Opcje: model, język
            <IconChevronDown
              size={13}
              stroke={2.25}
              className={`transition-transform ${optionsOpen ? "rotate-180" : ""}`}
            />
          </button>

          {withdrawn && !optionsOpen && (
            <p className="mt-1.5 text-[12px] text-major-text">
              Model {withdrawn} z Twoich ustawień nie jest już dostępny — użyję
              domyślnego.
            </p>
          )}

          {optionsOpen && (
            <div className="mt-3 flex gap-3 rounded-lg bg-surface-alt p-3.5">
              <div className="flex-1">
                <ModelSelect
                  value={model}
                  onChange={setModel}
                  className={optionInputClass}
                  labelClassName="mb-1 block text-[11.5px] text-muted"
                />
              </div>
              <label className="block flex-1">
                <span className="mb-1 block text-[11.5px] text-muted">Język</span>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className={optionInputClass}
                >
                  <option value="pl">Polski</option>
                  <option value="en">English</option>
                </select>
              </label>
            </div>
          )}

          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={() => void start()}
              disabled={running}
              data-testid="run-action"
              className="h-9 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
            >
              {running ? "Pracuje…" : "Uruchom"}
            </button>
            {running && (
              <button
                type="button"
                onClick={() => void cancel()}
                data-testid="cancel-action"
                className="h-9 rounded-lg border border-line px-4 text-[13px] font-medium text-critical-text hover:bg-surface-alt transition-colors"
              >
                Przerwij
              </button>
            )}
          </div>

          {shown && (
            <div className="mt-5 border-t border-line/60 pt-5">
              <p
                data-testid="action-status"
                className="mb-3.5 text-[11.5px] uppercase tracking-wide text-muted"
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
                  className="mt-4 h-9 rounded-lg border border-accent px-4 text-[13px] font-semibold text-accent-hover hover:bg-accent-soft transition-colors"
                >
                  {spec.acceptLabel ?? "Zaakceptuj"}
                </button>
              )}

              {shown.accepted && (
                <p className="mt-3 text-[13px] text-muted">Zaakceptowano.</p>
              )}
            </div>
          )}

          {error && (
            <p data-testid="action-panel-error" className="mt-3 text-[13px] text-critical-text">
              {error}
            </p>
          )}
        </div>
      )}
    </section>
  )
}
