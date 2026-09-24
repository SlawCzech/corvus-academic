"use client"

import { useState } from "react"
import useSWR from "swr"
import FileUpload from "@/components/FileUpload"
import ActionPanel from "@/components/students/ActionPanel"
import ActionResultView from "@/components/students/ActionResultView"
import DraftList from "@/components/students/DraftList"
import GuidelinePicker from "@/components/students/GuidelinePicker"
import StudentDetailsCard from "@/components/students/StudentDetailsCard"
import StudentSubNav, { type Section } from "@/components/students/StudentSubNav"
import TopicCard from "@/components/students/TopicCard"
import { createMeetingNote, fetcher, uploadDraft } from "@/lib/api.client"
import type { AgentAction, MeetingNote, Student, ThesisDraft } from "@/lib/api.types"

const ACTION_LABELS: Record<string, string> = {
  propose_topic: "Propozycja tematu",
  defence_questions: "Pytania na obronę",
  check_progress: "Sprawdzenie postępu",
  evaluate_methodology: "Ocena metodologii",
  draft_meeting_note: "Szkic notatki",
  generate_review: "Recenzja",
}

const STATUS_LABELS: Record<string, string> = {
  pending: "w kolejce",
  running: "w toku",
  completed: "gotowe",
  failed: "błąd",
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })
}

export default function StudentDetail({ studentId }: { studentId: string }) {
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
  const { data: actions } = useSWR<AgentAction[]>(actionsKey, fetcher)

  const [section, setSection] = useState<Section>("overview")
  const [openActionId, setOpenActionId] = useState<string | null>(null)
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
  if (!student) {
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

  async function addNote(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    if (!noteText.trim()) return
    await createMeetingNote(studentId, noteText)
    setNoteText("")
    void mutateNotes()
  }

  const hasReview = (actions ?? []).some(
    (a) => a.action_type === "generate_review" && a.status === "completed",
  )
  const latestDraft = drafts?.[0]

  return (
    <div className="flex min-h-screen">
      <StudentSubNav student={student} section={section} onSectionChange={setSection} />

      <main className="min-w-0 flex-1 px-10 py-10">
        {section === "overview" && (
          <div>
            <h1 className="mb-6 text-[24px] font-semibold text-foreground">Przegląd</h1>

            {latestDraft && !hasReview && (
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
                  onClick={() => setSection("actions")}
                  className="h-9 shrink-0 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors"
                >
                  Napisz recenzję
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
            </div>
          </div>
        )}

        {section === "actions" && (
          <div>
            <h1 className="mb-5 text-[24px] font-semibold text-foreground">Akcje AI</h1>
            <ActionPanel student={student} />
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
            {(actions ?? []).length === 0 ? (
              <p className="text-[13.5px] text-muted">Nic jeszcze nie uruchomiono.</p>
            ) : (
              <div className="rounded-xl border border-line bg-surface">
                {(actions ?? []).map((action, i) => {
                  const readable = action.output !== null || action.error !== null
                  const open = openActionId === action.id
                  return (
                    <div key={action.id}>
                      <button
                        type="button"
                        disabled={!readable}
                        aria-expanded={open}
                        onClick={() => setOpenActionId(open ? null : action.id)}
                        className={`flex w-full items-center justify-between px-4 py-3 text-left text-[13.5px] ${
                          i > 0 ? "border-t border-line/60" : ""
                        } ${
                          readable
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
                          {ACTION_LABELS[action.action_type] ?? action.action_type}
                          {action.accepted ? " · zaakceptowana" : ""}
                        </span>
                        <span className="text-muted">
                          {STATUS_LABELS[action.status] ?? action.status} ·{" "}
                          {formatDate(action.created_at)}
                        </span>
                      </button>
                      {open && (
                        <div
                          data-testid="history-result"
                          className="border-t border-line/60 bg-surface-alt/40 p-4"
                        >
                          <ActionResultView action={action} selected={0} onSelect={() => {}} />
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
