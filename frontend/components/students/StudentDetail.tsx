"use client"

import { useState } from "react"
import useSWR from "swr"
import FileUpload from "@/components/FileUpload"
import ActionPanel from "@/components/students/ActionPanel"
import ActionResultView from "@/components/students/ActionResultView"
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

  const { data: student, error } = useSWR<Student>(studentKey, fetcher)
  const { data: notes, mutate: mutateNotes } = useSWR<MeetingNote[]>(
    notesKey,
    fetcher,
  )
  const { data: drafts, mutate: mutateDrafts } = useSWR<ThesisDraft[]>(
    draftsKey,
    fetcher,
  )
  const { data: actions } = useSWR<AgentAction[]>(actionsKey, fetcher)

  const [openActionId, setOpenActionId] = useState<string | null>(null)
  const [noteText, setNoteText] = useState("")
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  if (error) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <p className="text-[13px] text-red-600">Nie znaleziono studenta.</p>
      </main>
    )
  }
  if (!student) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <p className="text-[13px] text-gray-500">Wczytywanie…</p>
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

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-50">
          {student.full_name}
        </h1>
        <p className="mt-1 text-[13px] text-gray-500">
          {student.field_of_study}
          {student.index_number ? ` · nr ${student.index_number}` : ""}
        </p>
        <p className="mt-3 text-[14px] text-gray-900 dark:text-gray-100">
          {student.current_topic ? (
            <>
              <span className="text-gray-400">Temat: </span>
              {student.current_topic}
            </>
          ) : (
            <span className="italic text-gray-400">Temat nieustalony</span>
          )}
        </p>
      </header>

      <ActionPanel student={student} />

      <section className="mb-10">
        <h2 className="mb-3 text-[15px] font-semibold text-gray-900 dark:text-gray-100">
          Wersje pracy
        </h2>
        <FileUpload onFileSelect={(file) => void handleUpload(file)} disabled={uploading} />
        {uploadError && (
          <p data-testid="upload-error" className="mt-2 text-[13px] text-red-600">
            {uploadError}
          </p>
        )}
        {drafts && drafts.length > 0 && (
          <ul className="mt-4 space-y-1 text-[13px]">
            {drafts.map((draft) => (
              <li key={draft.id} className="flex justify-between text-gray-600 dark:text-gray-400">
                <span>
                  <span className="font-medium text-gray-900 dark:text-gray-100">
                    v{draft.version_number}
                  </span>{" "}
                  {draft.filename}
                </span>
                <span className="text-gray-400">
                  {draft.char_count.toLocaleString("pl-PL")} znaków ·{" "}
                  {formatDate(draft.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mb-10">
        <h2 className="mb-3 text-[15px] font-semibold text-gray-900 dark:text-gray-100">
          Notatki ze spotkań
        </h2>
        <form onSubmit={addNote} className="mb-4">
          <textarea
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            rows={3}
            placeholder="Co ustaliliście na spotkaniu?"
            className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-[14px] text-gray-900 dark:text-gray-100 focus:border-gray-900 dark:focus:border-gray-300 focus:outline-none"
          />
          <button
            type="submit"
            className="mt-2 h-8 rounded-md border border-gray-300 dark:border-gray-700 px-4 text-[13px] text-gray-900 dark:text-gray-100"
          >
            Zapisz notatkę
          </button>
        </form>
        <ul className="space-y-3">
          {(notes ?? []).map((note) => (
            <li
              key={note.id}
              className="rounded-lg border border-gray-200 dark:border-gray-800 p-3"
            >
              <p className="text-[13px] text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                {note.content}
              </p>
              <p className="mt-2 text-[12px] text-gray-400">
                {formatDate(note.occurred_at)}
                {note.source_action_id ? " · szkic AI zaakceptowany" : ""}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="mb-3 text-[15px] font-semibold text-gray-900 dark:text-gray-100">
          Historia akcji
        </h2>
        {(actions ?? []).length === 0 ? (
          <p className="text-[13px] text-gray-500">Nic jeszcze nie uruchomiono.</p>
        ) : (
          <ul className="space-y-1 text-[13px]">
            {(actions ?? []).map((action) => {
              // Every finished action carries its whole result in `output`,
              // stored when it completed. Reading an old review is opening the
              // row, not running the model again.
              const readable = action.output !== null || action.error !== null
              const open = openActionId === action.id
              return (
                <li key={action.id}>
                  <button
                    type="button"
                    disabled={!readable}
                    aria-expanded={open}
                    onClick={() => setOpenActionId(open ? null : action.id)}
                    className={`flex w-full justify-between py-1 text-left text-gray-600 dark:text-gray-400 ${
                      readable
                        ? "hover:text-gray-900 dark:hover:text-gray-100"
                        : "cursor-default"
                    }`}
                  >
                    <span>
                      {readable && (
                        <span className="mr-1 inline-block w-3 text-gray-400">
                          {open ? "−" : "+"}
                        </span>
                      )}
                      {ACTION_LABELS[action.action_type] ?? action.action_type}
                      {action.accepted ? " · zaakceptowana" : ""}
                    </span>
                    <span className="text-gray-400">
                      {STATUS_LABELS[action.status] ?? action.status} ·{" "}
                      {formatDate(action.created_at)}
                    </span>
                  </button>
                  {open && (
                    <div
                      data-testid="history-result"
                      className="mb-3 rounded-lg border border-gray-200 dark:border-gray-800 p-3"
                    >
                      <ActionResultView
                        action={action}
                        selected={0}
                        onSelect={() => {}}
                      />
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </main>
  )
}
