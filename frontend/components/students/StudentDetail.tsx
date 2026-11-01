"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import FileUpload from "@/components/FileUpload"
import ActionPanel from "@/components/students/ActionPanel"
import ActionResultView from "@/components/students/ActionResultView"
import DeleteStudentPanel from "@/components/students/DeleteStudentPanel"
import DraftList from "@/components/students/DraftList"
import GuidelinePicker from "@/components/students/GuidelinePicker"
import LatestResults from "@/components/students/LatestResults"
import StudentDetailsCard from "@/components/students/StudentDetailsCard"
import type { Section } from "@/components/students/sections"
import StudentSubNav from "@/components/students/StudentSubNav"
import TopicCard from "@/components/students/TopicCard"
import WorkTimeline from "@/components/students/WorkTimeline"
import { ACTION_LABELS } from "@/components/students/format"
import { isUnfinished } from "@/hooks/useAction"
import { IconTrash } from "@tabler/icons-react"
import { createMeetingNote, deleteAction, fetcher, uploadDraft } from "@/lib/api.client"
import type {
  ActionType,
  AgentAction,
  MeetingNote,
  Student,
  ThesisDraft,
} from "@/lib/api.types"

const STATUS_LABELS: Record<string, string> = {
  pending: "w kolejce",
  running: "w toku",
  awaiting_input: "czeka na wybór uwag",
  completed: "gotowe",
  failed: "błąd",
  cancelled: "przerwana",
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })
}

/** Which version a final review will read, when that may surprise the promoter. */
function finalReviewNote(drafts: ThesisDraft[]): string | undefined {
  const newest = drafts.find((d) => !d.purged_at)
  const accepted = drafts.find((d) => d.is_accepted && !d.purged_at)
  if (!newest) return undefined
  if (!accepted) {
    return `Żadna wersja nie jest zaakceptowana jako finalna. Recenzja oceni najnowszą, wersję ${newest.version_number}.`
  }
  return accepted.id === newest.id
    ? undefined
    : `Recenzja oceni zaakceptowaną wersję ${accepted.version_number}, nie najnowszą.`
}

export default function StudentDetail({
  studentId,
  initialSection = "overview",
}: {
  studentId: string
  /** Where to open — the dashboard links straight to a waiting action. */
  initialSection?: Section
}) {
  const studentKey = `/api/students/${studentId}`
  const notesKey = `${studentKey}/meeting-notes`
  const draftsKey = `${studentKey}/drafts`
  const actionsKey = `${studentKey}/actions`

  const { data: student, error, mutate: mutateStudent } = useSWR<Student>(
    studentKey,
    fetcher,
  )
  const { data: notes, mutate: mutateNotes } = useSWR<MeetingNote[]>(
    notesKey,
    fetcher,
  )
  const { data: drafts, mutate: mutateDrafts } = useSWR<ThesisDraft[]>(
    draftsKey,
    fetcher,
  )
  const { data: actions, mutate: mutateActions } = useSWR<AgentAction[]>(actionsKey, fetcher)

  // The dashboard knows actions, not what they belong to: a one-off review
  // has its own page, and its links arrive here.
  const router = useRouter()
  const oneOff = student?.is_one_off === true
  useEffect(() => {
    if (oneOff) router.replace(`/reviews/${studentId}`)
  }, [oneOff, router, studentId])

  const [section, setSection] = useState<Section>(initialSection)
  // Which action the AI section opens on, when a suggestion led there.
  const [actionToOpen, setActionToOpen] = useState<ActionType | undefined>(undefined)
  const [openActionId, setOpenActionId] = useState<string | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [noteText, setNoteText] = useState("")
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  if (error) {
    return (
      <main className="px-12 py-10">
        <p className="text-[13px] text-critical-text">Nie znaleziono studenta.</p>
      </main>
    )
  }
  if (!student || oneOff) {
    return (
      <main className="px-12 py-10">
        <p className="text-[13px] text-muted">Wczytywanie…</p>
      </main>
    )
  }

  async function handleUpload(file: File): Promise<void> {
    setUploading(true)
    setUploadError(null)
    try {
      await uploadDraft(studentId, file)
      void mutateDrafts()
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Nie udało się wczytać")
    } finally {
      setUploading(false)
    }
  }

  async function removeAction(actionId: string): Promise<void> {
    setDeletingId(actionId)
    setHistoryError(null)
    try {
      await deleteAction(studentId, actionId)
      void mutateActions()
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : "Nie udało się usunąć akcji")
    } finally {
      setDeletingId(null)
      setConfirmDeleteId(null)
    }
  }

  async function addNote(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    if (!noteText.trim()) return
    await createMeetingNote(studentId, noteText)
    setNoteText("")
    void mutateNotes()
  }

  const hasReview = (actions ?? []).some(
    (a) =>
      (a.action_type === "generate_review" || a.action_type === "trial_review") &&
      a.status === "completed",
  )
  const latestDraft = drafts?.[0]
  const acceptedDraft = drafts?.find((d) => d.is_accepted && !d.purged_at)
  // Newest first. The way back to an action started before leaving the page.
  const unfinished = (actions ?? []).filter(isUnfinished)
  const reviewGoing = unfinished.some(
    (a) => a.action_type === "generate_review" || a.action_type === "trial_review",
  )
  const nextReview = acceptedDraft ? "generate_review" : "trial_review"
  const bibliographyTouched = (actions ?? []).some(
    (a) =>
      a.action_type === "verify_bibliography" &&
      (a.status === "completed" || isUnfinished(a)),
  )

  function openAction(type: ActionType): void {
    setActionToOpen(type)
    setSection("actions")
  }

  return (
    <div className="flex min-h-screen">
      <StudentSubNav
        student={student}
        section={section}
        onSectionChange={setSection}
        onStudentChange={(next) => void mutateStudent(next, { revalidate: false })}
      />

      <main className="min-w-0 flex-1 px-10 py-10">
        {section === "overview" && (
          <div>
            <h1 className="mb-6 text-[24px] font-semibold text-foreground">Przegląd</h1>

            {unfinished[0] && (
              <div
                data-testid="unfinished-banner"
                className="mb-5 flex items-center justify-between rounded-xl border border-accent bg-accent-soft p-5"
              >
                <div>
                  <span className="mb-0.5 block text-[13px] font-semibold text-accent-hover">
                    {unfinished[0].status === "awaiting_input"
                      ? "Recenzja czeka na Twój wybór uwag"
                      : "Akcja w toku"}
                  </span>
                  <span className="text-[13px] text-muted-strong">
                    {ACTION_LABELS[unfinished[0].action_type] ?? unfinished[0].action_type}
                    {unfinished.length > 1 ? ` i jeszcze ${unfinished.length - 1}` : ""}
                  </span>
                </div>
                <button
                  onClick={() => setSection("actions")}
                  className="h-9 shrink-0 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors"
                >
                  {unfinished[0].status === "awaiting_input" ? "Wybierz uwagi" : "Pokaż postęp"}
                </button>
              </div>
            )}

            {/* Not while one is being written: the banner above leads to it. */}
            {latestDraft && !hasReview && !reviewGoing && (
              <div className="mb-5 flex items-center justify-between rounded-xl border border-major-border bg-major-bg p-5">
                <div>
                  <span className="mb-0.5 block text-[13px] font-semibold text-major-text">
                    Sugerowany następny krok
                  </span>
                  <span className="text-[13px] text-muted-strong">
                    Wersja {latestDraft.version_number} pracy czeka na recenzję.
                  </span>
                </div>
                <button
                  onClick={() => openAction(nextReview)}
                  className="h-9 shrink-0 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors"
                >
                  {acceptedDraft ? "Recenzja finalna" : "Recenzja próbna"}
                </button>
              </div>
            )}

            {/* The review judges the choice of sources, not whether they exist. */}
            {latestDraft && hasReview && !bibliographyTouched && (
              <div
                data-testid="suggest-bibliography"
                className="mb-5 flex items-center justify-between rounded-xl border border-major-border bg-major-bg p-5"
              >
                <div>
                  <span className="mb-0.5 block text-[13px] font-semibold text-major-text">
                    Sugerowany następny krok
                  </span>
                  <span className="text-[13px] text-muted-strong">
                    Recenzja jest gotowa, ale nikt nie sprawdził, czy cytowane prace
                    istnieją.
                  </span>
                </div>
                <button
                  onClick={() => openAction("verify_bibliography")}
                  className="h-9 shrink-0 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors"
                >
                  Sprawdź bibliografię
                </button>
              </div>
            )}

            <div className="grid grid-cols-2 gap-5">
              <TopicCard
                student={student}
                onChange={(next) => void mutateStudent(next, { revalidate: false })}
                onAskAi={() => setSection("actions")}
              />

              <div className="rounded-xl border border-line bg-surface p-5">
                <h3 className="mb-3 text-[11.5px] font-semibold uppercase tracking-wide text-muted">
                  Postęp
                </h3>
                <div className="flex flex-col gap-2.5 text-[13.5px]">
                  <div className="flex items-center gap-2.5 text-foreground">
                    <span className="h-[7px] w-[7px] rounded-full bg-success-text" />
                    {(drafts ?? []).length} wersje pracy przesłane
                  </div>
                  <div className="flex items-center gap-2.5 text-foreground">
                    <span className="h-[7px] w-[7px] rounded-full bg-success-text" />
                    {(notes ?? []).length} notatek ze spotkań
                  </div>
                  <div
                    className={`flex items-center gap-2.5 ${
                      hasReview ? "text-foreground" : "text-accent"
                    }`}
                  >
                    <span
                      className={`h-[7px] w-[7px] rounded-full ${
                        hasReview ? "bg-success-text" : "bg-accent"
                      }`}
                    />
                    {hasReview ? "Recenzja napisana" : "Recenzja jeszcze nie napisana"}
                  </div>
                </div>
              </div>

              <GuidelinePicker
                student={student}
                onChange={(next) => void mutateStudent(next, { revalidate: false })}
              />

              <StudentDetailsCard
                student={student}
                onChange={(next) => void mutateStudent(next, { revalidate: false })}
              />

              <LatestResults
                actions={actions ?? []}
                onShowHistory={() => setSection("history")}
              />

              <DeleteStudentPanel student={student} />
            </div>
          </div>
        )}

        {section === "timeline" && (
          <WorkTimeline studentId={studentId} hasTopic={student.current_topic !== null} />
        )}

        {section === "actions" && (
          <div>
            <h1 className="mb-5 text-[24px] font-semibold text-foreground">Akcje AI</h1>
            <ActionPanel
              student={student}
              initialType={actionToOpen}
              notes={{ generate_review: finalReviewNote(drafts ?? []) }}
            />
          </div>
        )}

        {section === "drafts" && (
          <div>
            <h1 className="mb-5 text-[24px] font-semibold text-foreground">Wersje pracy</h1>
            <div className="mb-5">
              <FileUpload onFileSelect={(file) => void handleUpload(file)} disabled={uploading} />
            </div>
            {uploadError && (
              <p data-testid="upload-error" className="mb-4 text-[13px] text-critical-text">
                {uploadError}
              </p>
            )}
            <DraftList
              studentId={studentId}
              drafts={drafts ?? []}
              onChange={(next) => void mutateDrafts(next, { revalidate: false })}
            />
          </div>
        )}

        {section === "notes" && (
          <div>
            <h1 className="mb-5 text-[24px] font-semibold text-foreground">
              Notatki ze spotkań
            </h1>
            <form onSubmit={addNote} className="mb-5 rounded-xl border border-line bg-surface p-5">
              <textarea
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                rows={3}
                placeholder="Co ustaliliście na spotkaniu?"
                className="w-full rounded-lg border border-line bg-surface px-3.5 py-2 text-[14px] text-foreground focus:border-accent focus:outline-none"
              />
              <button
                type="submit"
                className="mt-3 h-9 rounded-lg border border-line px-4 text-[13px] font-medium text-foreground hover:bg-surface-alt transition-colors"
              >
                Zapisz notatkę
              </button>
            </form>
            <div className="flex flex-col gap-3">
              {(notes ?? []).map((note) => (
                <div key={note.id} className="rounded-xl border border-line bg-surface p-4">
                  <p className="whitespace-pre-wrap text-[13.5px] text-foreground">
                    {note.content}
                  </p>
                  <p className="mt-2.5 text-[12px] text-muted">
                    {formatDate(note.occurred_at)}
                    {note.source_action_id ? " · szkic AI zaakceptowany" : ""}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {section === "history" && (
          <div>
            <h1 className="mb-5 text-[24px] font-semibold text-foreground">Historia akcji</h1>
            {historyError && (
              <p role="alert" className="mb-4 text-[13px] text-critical-text">
                {historyError}
              </p>
            )}
            {(actions ?? []).length === 0 ? (
              <p className="text-[13.5px] text-muted">Nic jeszcze nie uruchomiono.</p>
            ) : (
              <div className="rounded-xl border border-line bg-surface">
                {(actions ?? []).map((action, i) => {
                  const going = isUnfinished(action)
                  const readable = !going && (action.output !== null || action.error !== null)
                  const open = openActionId === action.id
                  return (
                    <div
                      key={action.id}
                      data-testid="history-row"
                      className={i > 0 ? "border-t border-line/60" : ""}
                    >
                      <div className="flex items-center">
                        <button
                          type="button"
                          disabled={!readable && !going}
                          aria-expanded={going ? undefined : open}
                          title={going ? "Pokaż postęp" : undefined}
                          // An unfinished one has no result to unfold — it
                          // leads to where its progress is shown.
                          onClick={() =>
                            going ? setSection("actions") : setOpenActionId(open ? null : action.id)
                          }
                          className={`flex min-w-0 flex-1 items-center justify-between px-4 py-3 text-left text-[13.5px] ${
                            readable || going
                              ? "text-foreground hover:bg-surface-alt"
                              : "cursor-default text-muted"
                          }`}
                        >
                          <span>
                            {readable && (
                              <span className="mr-1.5 inline-block w-3 text-muted">
                                {open ? "−" : "+"}
                              </span>
                            )}
                            {going && <span className="mr-1.5 inline-block w-3 text-accent">→</span>}
                            {ACTION_LABELS[action.action_type] ?? action.action_type}
                            {action.accepted ? " · zaakceptowana" : ""}
                          </span>
                          <span className="text-muted">
                            {STATUS_LABELS[action.status] ?? action.status} ·{" "}
                            {formatDate(action.created_at)}
                          </span>
                        </button>
                        {confirmDeleteId === action.id ? (
                          <span className="flex shrink-0 items-center gap-1.5 pr-3">
                            <button
                              type="button"
                              disabled={deletingId === action.id}
                              onClick={() => void removeAction(action.id)}
                              className="h-7 rounded-md bg-critical-text px-2.5 text-[12px] font-semibold text-white disabled:opacity-50"
                            >
                              Usuń
                            </button>
                            <button
                              type="button"
                              onClick={() => setConfirmDeleteId(null)}
                              className="h-7 rounded-md border border-line px-2.5 text-[12px] text-foreground hover:bg-surface-alt"
                            >
                              Nie
                            </button>
                          </span>
                        ) : (
                          <button
                            type="button"
                            aria-label="Usuń z historii"
                            onClick={() => setConfirmDeleteId(action.id)}
                            className="shrink-0 px-3 py-3 text-muted hover:text-critical-text"
                          >
                            <IconTrash size={15} stroke={1.75} />
                          </button>
                        )}
                      </div>
                      {open && (
                        <div
                          data-testid="history-result"
                          className="border-t border-line/60 bg-surface-alt/40 p-4"
                        >
                          <ActionResultView action={action} />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
