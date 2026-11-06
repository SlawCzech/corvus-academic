"use client"

import { useState } from "react"
import GuidelineSetSelect from "@/components/guidelines/GuidelineSetSelect"
import { createStudent, updateStudent } from "@/lib/api.client"
import type { Student, ThesisType } from "@/lib/api.types"

const THESIS_TYPES: { value: ThesisType; label: string }[] = [
  { value: "bachelor", label: "Licencjacka" },
  { value: "master", label: "Magisterska" },
  { value: "master_article", label: "Magisterska (artykuł)" },
]

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
  const [thesisType, setThesisType] = useState<ThesisType>(student?.thesis_type ?? "bachelor")
  const [researchArea, setResearchArea] = useState(student?.research_area ?? "")
  const [researchAim, setResearchAim] = useState(student?.research_aim ?? "")
  const [guidelineSetId, setGuidelineSetId] = useState(student?.guideline_set_id ?? "")
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  // A set is for one kind of thesis: a new kind needs a new set.
  function chooseThesisType(next: ThesisType): void {
    setThesisType(next)
    setGuidelineSetId(next === student?.thesis_type ? (student.guideline_set_id ?? "") : "")
  }

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    setSaving(true)
    setError(null)
    const details = {
      full_name: fullName,
      field_of_study: fieldOfStudy,
      thesis_type: thesisType,
      research_area: researchArea.trim() || null,
      research_aim: researchAim.trim() || null,
      guideline_set_id: guidelineSetId,
    }
    try {
      if (editing) {
        onSaved(await updateStudent(student.id, details))
      } else {
        const created = await createStudent(details)
        setFullName("")
        setFieldOfStudy("")
        setResearchArea("")
        setResearchAim("")
        setGuidelineSetId("")
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
          <span className="mb-1 block text-[12px] text-muted">Typ pracy</span>
          <select
            value={thesisType}
            onChange={(e) => chooseThesisType(e.target.value as ThesisType)}
            className={inputClass}
          >
            {THESIS_TYPES.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="block sm:col-span-2">
          <span className="mb-1 block text-[12px] text-muted">Wytyczne uczelni</span>
          <GuidelineSetSelect
            thesisType={thesisType}
            value={guidelineSetId}
            onChange={setGuidelineSetId}
            className={inputClass}
            autoSelect
          />
        </label>
        <label className="block sm:col-span-2">
          <span className="mb-1 block text-[12px] text-muted">
            Obszar badawczy (opcjonalnie)
          </span>
          <input
            value={researchArea}
            onChange={(e) => setResearchArea(e.target.value)}
            maxLength={255}
            placeholder="np. ekonomia instytucjonalna, zarządzanie zasobami ludzkimi"
            className={inputClass}
          />
        </label>
        <label className="block sm:col-span-2">
          <span className="mb-1 block text-[12px] text-muted">
            Cel i hipotezy (opcjonalnie)
          </span>
          <textarea
            value={researchAim}
            onChange={(e) => setResearchAim(e.target.value)}
            maxLength={4000}
            rows={3}
            placeholder="Cel pracy i pytania badawcze lub hipotezy, tak jak je ustaliliście"
            className={inputClass}
          />
          <span className="mt-1 block text-[12px] text-muted">
            AI traktuje to jako kontekst, nie listę wymagań.
          </span>
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
