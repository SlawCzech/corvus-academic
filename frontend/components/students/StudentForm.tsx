"use client"

import { useState } from "react"
import { STUDENT_STATUS_LABELS } from "@/components/students/format"
import { createStudent, updateStudent } from "@/lib/api.client"
import type { Student, StudentStatus, ThesisType } from "@/lib/api.types"

const THESIS_TYPES: { value: ThesisType; label: string }[] = [
  { value: "bachelor", label: "Licencjacka" },
  { value: "master_article", label: "Magisterska (artykuł)" },
]

const STATUSES = Object.entries(STUDENT_STATUS_LABELS) as [StudentStatus, string][]

const inputClass =
  "w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[14px] " +
  "text-foreground focus:border-accent focus:outline-none"

interface StudentFormProps {
  /** Given: edit this student. Left out: add a new one. */
  student?: Student
  onSaved: (student: Student) => void
  onCancel?: () => void
}

export default function StudentForm({ student, onSaved, onCancel }: StudentFormProps) {
  const editing = student !== undefined
  const [fullName, setFullName] = useState(student?.full_name ?? "")
  const [fieldOfStudy, setFieldOfStudy] = useState(student?.field_of_study ?? "")
  const [indexNumber, setIndexNumber] = useState(student?.index_number ?? "")
  const [thesisType, setThesisType] = useState<ThesisType>(student?.thesis_type ?? "bachelor")
  const [status, setStatus] = useState<StudentStatus>(student?.status ?? "active")
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const dropsGuidelines =
    editing && student.guideline_set_id !== null && thesisType !== student.thesis_type

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    setSaving(true)
    setError(null)
    const details = {
      full_name: fullName,
      field_of_study: fieldOfStudy,
      thesis_type: thesisType,
      index_number: indexNumber.trim() || null,
    }
    try {
      if (editing) {
        onSaved(await updateStudent(student.id, { ...details, status }))
      } else {
        const created = await createStudent(details)
        setFullName("")
        setFieldOfStudy("")
        setIndexNumber("")
        onSaved(created)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać studenta")
    } finally {
      setSaving(false)
    }
  }

  return (
    <form
      onSubmit={submit}
      data-testid="student-form"
      className="mb-6 rounded-xl border border-line bg-surface p-5"
    >
      <h2 className="mb-3 text-[14px] font-semibold text-foreground">
        {editing ? "Dane studenta" : "Dodaj studenta"}
      </h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-[12px] text-muted">Imię i nazwisko</span>
          <input
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className={inputClass}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-[12px] text-muted">Kierunek</span>
          <input
            required
            value={fieldOfStudy}
            onChange={(e) => setFieldOfStudy(e.target.value)}
            className={inputClass}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-[12px] text-muted">Nr indeksu (opcjonalnie)</span>
          <input
            value={indexNumber}
            onChange={(e) => setIndexNumber(e.target.value)}
            className={inputClass}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-[12px] text-muted">Typ pracy</span>
          <select
            value={thesisType}
            onChange={(e) => setThesisType(e.target.value as ThesisType)}
            className={inputClass}
          >
            {THESIS_TYPES.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        {editing && (
          <label className="block">
            <span className="mb-1 block text-[12px] text-muted">Status</span>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as StudentStatus)}
              className={inputClass}
            >
              {STATUSES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {dropsGuidelines && (
        <p className="mt-3 text-[12.5px] text-major-text">
          Zmiana typu pracy wyczyści wybrany zestaw wytycznych — był dla poprzedniego typu.
        </p>
      )}
      {editing && status !== "active" && student.status === "active" && (
        <p className="mt-3 text-[12.5px] text-muted-strong">
          Zakończenie opieki uruchamia licznik retencji plików pracy.
        </p>
      )}

      {error && (
        <p data-testid="student-form-error" className="mt-3 text-[13px] text-critical-text">
          {error}
        </p>
      )}

      <div className="mt-4 flex gap-2">
        <button
          type="submit"
          disabled={saving}
          className="h-9 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
        >
          {saving ? "Zapisywanie…" : editing ? "Zapisz" : "Dodaj"}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="h-9 rounded-lg border border-line px-4 text-[13px] font-medium text-foreground hover:bg-surface-alt transition-colors"
          >
            Anuluj
          </button>
        )}
      </div>
    </form>
  )
}
