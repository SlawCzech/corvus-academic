"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useSWRConfig } from "swr"
import { deleteStudent } from "@/lib/api.client"
import type { Student } from "@/lib/api.types"

/**
 * Deleting a student for good, behind typing their name.
 *
 * Archiving is the everyday way to close a student: it keeps the record and
 * lets retention empty the files after five months. This is for the rest —
 * a student added by mistake, or one whose data has to go now.
 */
export default function DeleteStudentPanel({ student }: { student: Student }) {
  const router = useRouter()
  const { mutate } = useSWRConfig()
  const [open, setOpen] = useState(false)
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
      void mutate("/api/dashboard/summary")
      router.push("/students")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się usunąć studenta")
      setDeleting(false)
    }
  }

  if (!open) {
    return (
      <div className="col-span-2 text-right">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="text-[12.5px] text-muted hover:text-critical-text"
        >
          Usuń studenta
        </button>
      </div>
    )
  }

  return (
    <div
      data-testid="delete-student"
      className="col-span-2 rounded-xl border border-critical-border bg-critical-bg p-5"
    >
      <h3 className="mb-2 text-[13.5px] font-semibold text-critical-text">
        Usunąć {student.full_name} na zawsze?
      </h3>
      <p className="text-[13px] text-muted-strong">
        Znikną notatki ze spotkań, wszystkie wersje pracy razem z plikami i wszystkie wyniki AI —
        także po stronie serwisu AI. Tego nie da się cofnąć.
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
          onClick={() => {
            setOpen(false)
            setTyped("")
            setError(null)
          }}
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
