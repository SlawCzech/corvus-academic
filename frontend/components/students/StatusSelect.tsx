"use client"

import { useState } from "react"
import { STUDENT_STATUS_LABELS, STUDENT_STATUS_STYLES } from "@/components/students/format"
import { updateStudent } from "@/lib/api.client"
import type { Student, StudentStatus } from "@/lib/api.types"

const STATUSES = Object.entries(STUDENT_STATUS_LABELS) as [StudentStatus, string][]

interface Props {
  student: Student
  onChange: (student: Student) => void
}

/**
 * The student's status badge, which is also where the status is changed.
 *
 * One click, saved at once — closing supervision is an everyday step, not an
 * edit of the student's details. It is reversible: back to "Aktywny" stops
 * the retention clock that leaving it started.
 */
export default function StatusSelect({ student, onChange }: Props) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function change(status: StudentStatus): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      onChange(await updateStudent(student.id, { status }))
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zmienić statusu")
    } finally {
      setSaving(false)
    }
  }

  return (
    <span className="inline-flex flex-col items-start">
      <select
        aria-label={`Status: ${student.full_name}`}
        value={student.status}
        disabled={saving}
        onChange={(e) => void change(e.target.value as StudentStatus)}
        title={
          student.status === "active"
            ? "Zmiana na Obroniony lub Archiwalny uruchamia licznik retencji plików pracy"
            : "Powrót do Aktywny zatrzymuje licznik retencji"
        }
        className={`cursor-pointer appearance-none rounded-full border-0 py-0.5 pl-2.5 pr-6 text-[12px] font-medium focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-60 ${STUDENT_STATUS_STYLES[student.status]}`}
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%23888888' stroke-width='3'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E\")",
          backgroundRepeat: "no-repeat",
          backgroundPosition: "right 8px center",
        }}
      >
        {STATUSES.map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      {error && (
        <span role="alert" className="mt-1 text-[12px] text-critical-text">
          {error}
        </span>
      )}
    </span>
  )
}
