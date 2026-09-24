"use client"

import { useState } from "react"
import { updateStudent } from "@/lib/api.client"
import type { Student } from "@/lib/api.types"

interface Props {
  student: Student
  onChange: (student: Student) => void
  /** Take the promoter to the AI topic proposals instead of typing one. */
  onAskAi: () => void
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })
}

/**
 * The thesis topic, settled by hand. Accepting an AI proposal writes the same
 * field — this is the way for a topic agreed with the student in person.
 */
export default function TopicCard({ student, onChange, onAskAi }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function startEditing(): void {
    setDraft(student.current_topic ?? "")
    setError(null)
    setEditing(true)
  }

  async function save(topic: string | null): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      onChange(await updateStudent(student.id, { current_topic: topic }))
      setEditing(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać tematu")
    } finally {
      setSaving(false)
    }
  }

  const secondaryButton =
    "h-8 rounded-lg border border-line px-3 text-[12.5px] font-medium text-foreground " +
    "hover:bg-surface-alt transition-colors disabled:opacity-50"

  return (
    <div data-testid="topic-card" className="rounded-xl border border-line bg-surface p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[11.5px] font-semibold uppercase tracking-wide text-muted">
          Temat pracy
        </h3>
        {!editing && (
          <button
            type="button"
            onClick={startEditing}
            className="text-[12.5px] text-accent hover:underline"
          >
            {student.current_topic ? "Zmień" : "Wpisz temat"}
          </button>
        )}
      </div>

      {editing ? (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (draft.trim()) void save(draft)
          }}
        >
          <textarea
            aria-label="Temat pracy"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={3}
            autoFocus
            placeholder="Temat ustalony ze studentem"
            className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-[14px] text-foreground focus:border-accent focus:outline-none"
          />
          <div className="mt-2.5 flex flex-wrap gap-2">
            <button
              type="submit"
              disabled={saving || !draft.trim()}
              className="h-8 rounded-lg bg-accent px-3 text-[12.5px] font-semibold text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
            >
              {saving ? "Zapisywanie…" : "Zapisz temat"}
            </button>
            <button type="button" onClick={() => setEditing(false)} className={secondaryButton}>
              Anuluj
            </button>
            {student.current_topic && (
              <button
                type="button"
                disabled={saving}
                onClick={() => void save(null)}
                className={`${secondaryButton} ml-auto text-critical-text`}
              >
                Usuń temat
              </button>
            )}
          </div>
        </form>
      ) : student.current_topic ? (
        <>
          <p className="text-[15px] leading-relaxed text-foreground">{student.current_topic}</p>
          {student.current_topic_set_at && (
            <p className="mt-2.5 text-[12.5px] text-muted">
              Ustalony {formatDate(student.current_topic_set_at)}
            </p>
          )}
        </>
      ) : (
        <>
          <p className="text-[13.5px] italic text-muted">Temat nieustalony</p>
          <button
            type="button"
            onClick={onAskAi}
            className="mt-2.5 text-[12.5px] text-muted-strong hover:text-accent"
          >
            albo poproś AI o propozycje →
          </button>
        </>
      )}

      {error && (
        <p role="alert" className="mt-2 text-[13px] text-critical-text">
          {error}
        </p>
      )}
    </div>
  )
}
