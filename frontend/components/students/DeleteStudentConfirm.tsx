"use client"

import { useState } from "react"
import { useSWRConfig } from "swr"
import { deleteStudent } from "@/lib/api.client"
import type { Student } from "@/lib/api.types"

interface Props {
  student: Student
  onDeleted: () => void
  onCancel: () => void
}

/**
 * Deleting a student for good, behind typing their name.
 *
 * Archiving is the everyday way to close a student: it keeps the record and
 * lets retention empty the files after five months. This is for the rest —
 * a student added by mistake, or one whose data has to go now. Shared by the
 * student's overview and the roster, so both ask the same way.
 */
export default function DeleteStudentConfirm({ student, onDeleted, onCancel }: Props) {
  const { mutate } = useSWRConfig()
  const [typed, setTyped] = useState("")
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const confirmed = typed.trim() === student.full_name

  async function remove(): Promise<void> {
    setDeleting(true)
    setError(null)
    try {
      await deleteStudent(student.id)
      void mutate("/api/students")
      void mutate("/api/reviews")
      void mutate("/api/dashboard/summary")
      onDeleted()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się usunąć studenta")
      setDeleting(false)
    }
  }

  return (
    <div
      data-testid="delete-student"
      className="rounded-xl border border-critical-border bg-critical-bg p-5"
    >
      <h3 className="mb-2 text-[13.5px] font-semibold text-critical-text">
        Usunąć {student.full_name} na zawsze?
      </h3>
      <p className="text-[13px] text-muted-strong">
        {student.is_one_off
          ? "Znikną praca razem z plikiem i wszystkie wyniki AI"
          : "Znikną notatki ze spotkań, wszystkie wersje pracy razem z plikami i wszystkie wyniki AI"}{" "}
        — także po stronie serwisu AI. Tego nie da się cofnąć.
      </p>
      {student.status === "active" && (
        <p className="mt-2 text-[13px] text-muted-strong">
          Jeśli opieka się po prostu skończyła, zmień status na „Obroniony” albo „Archiwalny” — dane
          zostaną, a pliki prac usunie retencja po pięciu miesiącach.
        </p>
      )}
      <label className="mt-3.5 block">
        <span className="mb-1 block text-[12px] text-muted-strong">
          Wpisz <strong>{student.full_name}</strong>, żeby potwierdzić
        </span>
        <input
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          autoFocus
          className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[14px] text-foreground focus:border-critical-text focus:outline-none"
        />
      </label>
      <div className="mt-3.5 flex gap-2">
        <button
          type="button"
          disabled={!confirmed || deleting}
          onClick={() => void remove()}
          className="h-9 rounded-lg bg-critical-text px-4 text-[13px] font-semibold text-white transition-opacity disabled:opacity-40"
        >
          {deleting ? "Usuwanie…" : "Usuń na zawsze"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="h-9 rounded-lg border border-line bg-surface px-4 text-[13px] font-medium text-foreground hover:bg-surface-alt"
        >
          Anuluj
        </button>
      </div>
      {error && (
        <p role="alert" className="mt-3 text-[13px] text-critical-text">
          {error}
        </p>
      )}
    </div>
  )
}
