"use client"

import { useState } from "react"
import useSWR, { useSWRConfig } from "swr"
import ActionProgress from "./ActionProgress"
import FindingPicker from "./FindingPicker"
import ModelSelect, { useModelChoice } from "@/components/ai/ModelSelect"
import ReviewToneChoice from "@/components/ai/ReviewToneChoice"
import ActionResultView from "@/components/students/ActionResultView"
import GuidelinePicker from "@/components/students/GuidelinePicker"
import { isUnfinished, useAction } from "@/hooks/useAction"
import { useAiDefaults, type AiDefaults } from "@/lib/aiDefaults"
import { fetcher } from "@/lib/api.client"
import type { ActionType, AgentAction, Student } from "@/lib/api.types"

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
    type: "verify_bibliography",
    label: "Sprawdź bibliografię",
    hint: "Czy cytowane prace istnieją (Crossref)",
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
  awaiting_input: "Czeka na Twój wybór uwag",
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
  const { data: actions } = useSWR<AgentAction[]>(
    `/api/students/${student.id}/actions`,
    fetcher,
  )
  // Newest first, as the server lists them.
  const unfinished = Array.isArray(actions) ? actions.filter(isUnfinished) : []
  // Remounts once the real (possibly non-fallback) defaults are known, so the
  // panel's local option state starts from them without an effect.
  return (
    <ActionPanelInner
      key={`${defaults.model}:${defaults.language}:${defaults.reviewTone}`}
      student={student}
      defaults={defaults}
      unfinished={unfinished}
    />
  )
}

function ActionPanelInner({
  student,
  defaults,
  unfinished,
}: {
  student: Student
  defaults: AiDefaults
  /** Actions still queued, running or waiting for the promoter, newest first. */
  unfinished: AgentAction[]
}) {
  const { action, running, error, run, accept, cancel, resume, watch, dismiss } = useAction(
    student.id,
  )
  const { mutate } = useSWRConfig()
  const [selectedType, setSelectedType] = useState<ActionType | null>(null)
  // Coming back to the page while something runs: open on it, not on nothing.
  // Only while nothing is chosen — the list of actions may arrive after the
  // promoter's first click, and that click wins. Set during render, the way
  // React asks for state derived from a prop that changed.
  const resumable = unfinished[0]
  const [adoptedId, setAdoptedId] = useState<string | null>(null)
  if (resumable && selectedType === null && adoptedId !== resumable.id) {
    setAdoptedId(resumable.id)
    setSelectedType(resumable.action_type)
    watch(resumable.id)
  }
  const [detail, setDetail] = useState("")
  const [topicIndex, setTopicIndex] = useState(0)

  const [model, setModel] = useState(defaults.model)
  const [language, setLanguage] = useState(defaults.language)
  const [reviewTone, setReviewTone] = useState(defaults.reviewTone)
  const [findingsFirst, setFindingsFirst] = useState(false)
  // What actually gets sent: a saved model the admin has since withdrawn, or
  // a provider whose key was removed, falls back to the default local model
  // rather than getting the action refused.
  const { provider, model: effectiveModel } = useModelChoice(model)

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
      provider,
      model: effectiveModel,
      language,
      reviewTone,
      reviewFindingsFirst: selectedType === "generate_review" && findingsFirst,
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
              // One of this kind still going: show it, rather than a blank form.
              const going = unfinished.find((u) => u.action_type === a.type)
              if (going) watch(going.id)
              else dismiss()
            }}
            className={`flex h-9 items-center gap-2 rounded-lg border px-3.5 text-[13px] font-medium transition-colors ${
              selectedType === a.type
                ? "border-accent bg-accent-soft text-accent-hover"
                : "border-line text-muted-strong hover:text-foreground"
            }`}
          >
            {a.label}
            {unfinished.some((u) => u.action_type === a.type) && (
              <span
                data-testid={`unfinished-${a.type}`}
                title="W toku"
                className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent"
              />
            )}
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
              <label className="mt-3 flex cursor-pointer items-center gap-2 text-[13px] text-muted-strong">
                <input
                  type="checkbox"
                  checked={findingsFirst}
                  onChange={(e) => setFindingsFirst(e.target.checked)}
                  data-testid="findings-first"
                  className="accent-accent"
                />
                Pokaż mi uwagi, zanim powstanie recenzja
              </label>
            </div>
          )}

          {/* Always in view: which model an action runs on is not a detail. */}
          <div className="mt-3.5 flex gap-3 rounded-lg bg-surface-alt p-3.5">
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

              {shown.progress && (shown.status === "pending" || shown.status === "running") && (
                <ActionProgress progress={shown.progress} />
              )}

              {shown.status === "awaiting_input" ? (
                <FindingPicker
                  findings={shown.output?.findings ?? []}
                  onSubmit={(kept) => void resume(kept)}
                />
              ) : (
                <ActionResultView
                  action={shown}
                  selected={topicIndex}
                  onSelect={setTopicIndex}
                />
              )}

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
