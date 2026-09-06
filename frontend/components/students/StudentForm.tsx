"use client"

import { useState } from "react"
import { createStudent } from "@/lib/api.client"
import type { ThesisType } from "@/lib/api.types"

const THESIS_TYPES: { value: ThesisType; label: string }[] = [
  { value: "bachelor", label: "Licencjacka" },
  { value: "master_article", label: "Magisterska (artykuł)" },
]

const inputClass =
  "w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white " +
  "dark:bg-gray-900 px-3 py-1.5 text-[14px] text-gray-900 dark:text-gray-100 " +
  "focus:border-gray-900 dark:focus:border-gray-300 focus:outline-none"

export default function StudentForm({ onCreated }: { onCreated: () => void }) {
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
      className="mb-8 rounded-lg border border-gray-200 dark:border-gray-800 p-4"
    >
      <h2 className="mb-3 text-[14px] font-medium text-gray-900 dark:text-gray-100">
        Dodaj studenta
      </h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-[12px] text-gray-500">Imię i nazwisko</span>
          <input
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className={inputClass}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-[12px] text-gray-500">Kierunek</span>
          <input
            required
            value={fieldOfStudy}
            onChange={(e) => setFieldOfStudy(e.target.value)}
            className={inputClass}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-[12px] text-gray-500">
            Nr indeksu (opcjonalnie)
          </span>
          <input
            value={indexNumber}
            onChange={(e) => setIndexNumber(e.target.value)}
            className={inputClass}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-[12px] text-gray-500">Typ pracy</span>
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
        <p data-testid="student-form-error" className="mt-3 text-[13px] text-red-600">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={saving}
        className="mt-4 h-8 rounded-md bg-gray-900 dark:bg-white px-4 text-[13px] font-medium text-white dark:text-gray-900 disabled:opacity-50"
      >
        {saving ? "Zapisywanie…" : "Dodaj"}
      </button>
    </form>
  )
}
