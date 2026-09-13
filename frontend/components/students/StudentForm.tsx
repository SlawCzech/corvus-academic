"use client"

import { useState } from "react"
import { createStudent } from "@/lib/api.client"
import type { ThesisType } from "@/lib/api.types"

const THESIS_TYPES: { value: ThesisType; label: string }[] = [
  { value: "bachelor", label: "Licencjacka" },
  { value: "master_article", label: "Magisterska (artykuł)" },
]

const inputClass =
  "w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[14px] " +
  "text-foreground focus:border-accent focus:outline-none"

interface StudentFormProps {
  onCreated: () => void
  onCancel?: () => void
}

export default function StudentForm({ onCreated, onCancel }: StudentFormProps) {
  const [fullName, setFullName] = useState("")
  const [fieldOfStudy, setFieldOfStudy] = useState("")
  const [indexNumber, setIndexNumber] = useState("")
  const [thesisType, setThesisType] = useState<ThesisType>("bachelor")
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await createStudent({
        full_name: fullName,
        field_of_study: fieldOfStudy,
        thesis_type: thesisType,
        index_number: indexNumber || null,
      })
      setFullName("")
      setFieldOfStudy("")
      setIndexNumber("")
      onCreated()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się dodać studenta")
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
        Dodaj studenta
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
          <span className="mb-1 block text-[12px] text-muted">
            Nr indeksu (opcjonalnie)
          </span>
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
      </div>

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
          {saving ? "Zapisywanie…" : "Dodaj"}
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
