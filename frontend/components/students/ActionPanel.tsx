"use client"

import { Fragment, useState } from "react"
import useSWR, { useSWRConfig } from "swr"
import {
  IconBooks,
  IconBulb,
  IconFileSearch,
  IconFileText,
  IconGitCompare,
  IconLayoutGrid,
  IconMail,
  IconMessageQuestion,
  IconMicroscope,
  IconNotes,
} from "@tabler/icons-react"
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
  icon: typeof IconBulb
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
    icon: IconBulb,
    detailLabel: "Wskazówki dla modelu (opcjonalnie)",
    acceptable: true,
    acceptLabel: "Ustaw jako temat pracy",
  },
  {
    type: "draft_meeting_note",
    label: "Spisz notatkę",
    hint: "Notatka ze spotkania z twoich skrótów",
    icon: IconNotes,
    detailLabel: "Skrócone punkty ze spotkania",
    acceptable: true,
    acceptLabel: "Zapisz jako notatkę",
  },
  {
    type: "check_progress",
    label: "Sprawdź postęp",
    hint: "Porównanie dwóch ostatnich wersji",
    icon: IconGitCompare,
  },
  {
    type: "evaluate_methodology",
    label: "Oceń metodologię",
    hint: "Uwagi do metody i doboru źródeł",
    icon: IconMicroscope,
  },
  {
    type: "verify_bibliography",
    label: "Sprawdź bibliografię",
    hint: "Czy cytowane prace istnieją — Crossref i katalogi bibliotek",
    icon: IconBooks,
  },
  {
    type: "trial_review",
    label: "Recenzja próbna",
    hint: "Co poprawić przed złożeniem pracy",
    icon: IconFileSearch,
  },
  {
    type: "draft_student_email",
    label: "Mail do studenta",
    hint: "Szkic maila z najnowszej recenzji próbnej",
    icon: IconMail,
    detailLabel: "Co dodać od siebie (opcjonalnie)",
  },
  {
    type: "generate_review",
    label: "Recenzja finalna",
    hint: "Ocena gotowej pracy do systemu uczelni",
    icon: IconFileText,
  },
  {
    type: "defence_questions",
    label: "Pytania na obronę",
    hint: "Trzy ogólne pytania o pracę",
    icon: IconMessageQuestion,
  },
]

// In the order a thesis goes through them. Grouped because seven tiles in a
// row say nothing about which one is for now.
const STAGES: { title: string; note: string; types: ActionType[] }[] = [
  {
    title: "Praca nad tekstem",
    note: "Od tematu po kolejne wersje",
    types: ["propose_topic", "draft_meeting_note", "check_progress"],
  },
  {
    title: "Gotowa całość",
    note: "Gdy jest już cała praca",
    types: [
      "evaluate_methodology",
      "verify_bibliography",
      "trial_review",
      "draft_student_email",
      "generate_review",
    ],
  },
  {
    title: "Obrona",
    note: "Przygotowanie do egzaminu",
    types: ["defence_questions"],
  },
]

function actionsOf(types: ActionType[]): ActionSpec[] {
  return ACTIONS.filter((a) => types.includes(a.type))
}

function stagesFor(only?: ActionType[]): typeof STAGES {
  if (!only) return STAGES
  return STAGES.map((stage) => ({
    ...stage,
    types: stage.types.filter((type) => only.includes(type)),
  })).filter((stage) => stage.types.length > 0)
}

const STATUS_LABELS: Record<string, string> = {
  pending: "W kolejce",
  running: "Liczy się…",
  awaiting_input: "Czeka na Twój wybór uwag",
  completed: "Gotowe",
  failed: "Błąd",
  cancelled: "Przerwano",
}

/** Judged against university requirements — the chosen set matters here. */
const USES_GUIDELINES: ActionType[] = ["generate_review", "trial_review", "evaluate_methodology"]

/** The whole graph, with a pause to pick the findings if asked. */
const FULL_REVIEWS: ActionType[] = ["generate_review", "trial_review"]

const optionInputClass =
  "w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[13.5px] " +
  "text-foreground focus:border-accent focus:outline-none"

export default function ActionPanel({
  student,
  initialType,
  only,
  notes,
}: {
  student: Student
  /** Open on this action — a suggestion elsewhere on the page led here. */
  initialType?: ActionType
  /** Offer just these: a one-off review takes fewer actions than a student. */
  only?: ActionType[]
  /** A word on what a chosen action will work from, when that is not obvious. */
  notes?: Partial<Record<ActionType, string>>
}) {
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
      bibliographyChecked={
        Array.isArray(actions) &&
        actions.some((a) => a.action_type === "verify_bibliography" && a.status === "completed")
      }
      initialType={initialType}
      stages={stagesFor(only)}
      notes={notes}
    />
  )
}

function ActionPanelInner({
  student,
  defaults,
  unfinished,
  bibliographyChecked,
  initialType,
  stages,
  notes,
}: {
  student: Student
  defaults: AiDefaults
  /** Actions still queued, running or waiting for the promoter, newest first. */
  unfinished: AgentAction[]
  /** Whether the student's references were ever checked against the catalogues. */
  bibliographyChecked: boolean
  initialType?: ActionType
  stages: typeof STAGES
  notes?: Partial<Record<ActionType, string>>
}) {
  const { action, running, error, run, accept, cancel, resume, watch, dismiss } = useAction(
    student.id,
  )
  const { mutate } = useSWRConfig()
  const [selectedType, setSelectedType] = useState<ActionType | null>(initialType ?? null)
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
  // What actually gets sent: a provider whose key was removed is never
  // swapped for the other one — the run button waits for a key instead.
  const { provider, needsKey } = useModelChoice(model)

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
      language,
      reviewTone,
      reviewFindingsFirst: FULL_REVIEWS.includes(selectedType) && findingsFirst,
    })
  }

  function choose(type: ActionType): void {
    setSelectedType(type)
    setDetail("")
    // One of this kind still going: show it, rather than a blank form.
    const going = unfinished.find((u) => u.action_type === type)
    if (going) watch(going.id)
    else dismiss()
  }

  const goingDot = (type: ActionType) =>
    unfinished.some((u) => u.action_type === type) && (
      <span
        data-testid={`unfinished-${type}`}
        title="W toku"
        className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-accent"
      />
    )

  return (
    <section>
      {selectedType === null ? (
        // Nothing chosen: the whole catalogue, with room to say what each does.
        <div data-testid="action-tiles" className="space-y-6">
          {stages.map((stage) => (
            <section key={stage.title} aria-label={stage.title}>
              <div className="mb-2.5 flex items-baseline gap-2.5">
                <h3 className="text-[13.5px] font-semibold text-foreground">{stage.title}</h3>
                <p className="text-[12.5px] text-muted">{stage.note}</p>
              </div>
              <div className="grid grid-cols-3 gap-3">
                {actionsOf(stage.types).map((a) => (
                  <button
                    key={a.type}
                    type="button"
                    aria-label={a.label}
                    onClick={() => choose(a.type)}
                    className="group flex flex-col rounded-xl border border-line bg-surface p-4 text-left transition-colors hover:border-accent"
                  >
                    <span className="mb-2.5 flex items-center justify-between">
                      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-soft text-accent-hover">
                        <a.icon size={18} stroke={1.75} />
                      </span>
                      {goingDot(a.type)}
                    </span>
                    <span className="block text-[14px] font-semibold text-foreground group-hover:text-accent-hover">
                      {a.label}
                    </span>
                    <span className="mt-0.5 block text-[12.5px] leading-snug text-muted-strong">
                      {a.hint}
                    </span>
                  </button>
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : (
        // One chosen: the catalogue shrinks to a strip, out of the work's way.
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            aria-label="Wszystkie akcje"
            title="Wszystkie akcje"
            onClick={() => {
              setSelectedType(null)
              dismiss()
            }}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-line text-muted-strong hover:text-foreground"
          >
            <IconLayoutGrid size={16} stroke={1.75} />
          </button>
          {stages.map((stage, index) => (
            <Fragment key={stage.title}>
              {index > 0 && <span aria-hidden className="mx-1 h-5 w-px bg-line" />}
              {actionsOf(stage.types).map((a) => (
                <button
                  key={a.type}
                  type="button"
                  title={a.hint}
                  onClick={() => choose(a.type)}
                  className={`flex h-9 items-center gap-2 rounded-lg border px-3 text-[13px] font-medium transition-colors ${
                    selectedType === a.type
                      ? "border-accent bg-accent-soft text-accent-hover"
                      : "border-line text-muted-strong hover:text-foreground"
                  }`}
                >
                  <a.icon size={15} stroke={1.75} />
                  {a.label}
                  {goingDot(a.type)}
                </button>
              ))}
            </Fragment>
          ))}
        </div>
      )}

      {spec && (
        <div className="mt-4 rounded-xl border border-line bg-surface p-5">
          <p className="text-[13.5px] text-muted-strong">{spec.hint}</p>

          {selectedType && notes?.[selectedType] && (
            <p data-testid="action-note" className="mt-2 text-[12.5px] text-major-text">
              {notes[selectedType]}
            </p>
          )}

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

          {selectedType && FULL_REVIEWS.includes(selectedType) && (
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
              disabled={running || needsKey}
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

              {shown.action_type === "trial_review" && shown.status === "completed" && (
                <div
                  data-testid="suggest-email"
                  className="mt-5 flex items-center justify-between gap-4 rounded-lg border border-line bg-surface-alt p-3.5"
                >
                  <p className="text-[13px] text-muted-strong">
                    Z tej recenzji powstanie szkic maila do studenta, bez punktów i oceny.
                  </p>
                  <button
                    type="button"
                    onClick={() => choose("draft_student_email")}
                    className="flex h-9 shrink-0 items-center gap-2 rounded-lg border border-accent px-3.5 text-[13px] font-semibold text-accent-hover hover:bg-accent-soft transition-colors"
                  >
                    <IconMail size={15} stroke={1.75} />
                    Napisz mail
                  </button>
                </div>
              )}

              {FULL_REVIEWS.includes(shown.action_type) &&
                shown.status === "completed" &&
                !bibliographyChecked && (
                  <div
                    data-testid="suggest-bibliography"
                    className="mt-5 flex items-center justify-between gap-4 rounded-lg border border-line bg-surface-alt p-3.5"
                  >
                    <p className="text-[13px] text-muted-strong">
                      Recenzja ocenia dobór źródeł, ale nie sprawdza, czy cytowane
                      prace istnieją. To osobny krok.
                    </p>
                    <button
                      type="button"
                      onClick={() => choose("verify_bibliography")}
                      className="flex h-9 shrink-0 items-center gap-2 rounded-lg border border-accent px-3.5 text-[13px] font-semibold text-accent-hover hover:bg-accent-soft transition-colors"
                    >
                      <IconBooks size={15} stroke={1.75} />
                      Sprawdź bibliografię
                    </button>
                  </div>
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
