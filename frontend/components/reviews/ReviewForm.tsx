"use client"

import { useRef, useState } from "react"
import FileUpload from "@/components/FileUpload"
import GuidelineSetSelect from "@/components/guidelines/GuidelineSetSelect"
import { createReview, readTitlePage } from "@/lib/api.client"
import type { Review, ThesisType } from "@/lib/api.types"

const inputClass =
  "w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[14px] " +
  "text-foreground focus:border-accent focus:outline-none"

interface ReviewFormProps {
  onCreated: (review: Review) => void
  onCancel: () => void
}

/** A thesis to review once: what the review needs to know, and the file. */
export default function ReviewForm({ onCreated, onCancel }: ReviewFormProps) {
  const [file, setFile] = useState<File | null>(null)
  const [fullName, setFullName] = useState("")
  const [fieldOfStudy, setFieldOfStudy] = useState("")
  const [thesisType, setThesisType] = useState<ThesisType>("bachelor")
  const [topic, setTopic] = useState("")
  const [researchArea, setResearchArea] = useState("")
  const [researchAim, setResearchAim] = useState("")
  const [guidelineSetId, setGuidelineSetId] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [suggested, setSuggested] = useState(false)
  // The promoter's own choice wins over a title page read after it.
  const typeChosen = useRef(false)
  // Only the latest file's title page counts: a slower, older one must not
  // land on top of it.
  const lastFile = useRef<File | null>(null)

  async function chooseFile(chosen: File): Promise<void> {
    setFile(chosen)
    setSuggested(false)
    lastFile.current = chosen
    try {
      const page = await readTitlePage(chosen)
      if (lastFile.current !== chosen) return
      // Only what is still empty: whatever was typed stays.
      if (page.full_name) setFullName((v) => v || (page.full_name ?? ""))
      if (page.field_of_study) setFieldOfStudy((v) => v || (page.field_of_study ?? ""))
      if (page.current_topic) setTopic((v) => v || (page.current_topic ?? ""))
      if (page.thesis_type && !typeChosen.current && page.thesis_type !== thesisType) {
        setThesisType(page.thesis_type)
        setGuidelineSetId("")
      }
      setSuggested(Boolean(page.full_name || page.field_of_study || page.current_topic))
    } catch {
      // A hint that did not arrive: the form is still there to fill in, and
      // a file nobody can read says so on sending.
    }
  }

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    if (!file) {
      setError("Wybierz plik z pracą")
      return
    }
    setSaving(true)
    setError(null)
    try {
      onCreated(
        await createReview(
          {
            full_name: fullName,
            field_of_study: fieldOfStudy,
            thesis_type: thesisType,
            current_topic: topic.trim(),
            research_area: researchArea.trim(),
            research_aim: researchAim.trim(),
            guideline_set_id: guidelineSetId,
          },
          file,
        ),
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać recenzji")
      setSaving(false)
    }
  }

  return (
    <form
      onSubmit={submit}
      data-testid="review-form"
      className="mb-6 rounded-xl border border-line bg-surface p-5"
    >
      <h2 className="mb-3 text-[14px] font-semibold text-foreground">Nowa recenzja</h2>
      <div className="mb-3">
        <FileUpload
          onFileSelect={(chosen) => void chooseFile(chosen)}
          disabled={saving}
          prompt="Upuść pracę (PDF lub DOCX)"
        />
      </div>
      {suggested && (
        <p data-testid="title-page-note" className="mb-3 text-[12.5px] text-muted-strong">
          Uzupełniono ze strony tytułowej. Sprawdź, zanim przejdziesz dalej: autor i tytuł trafią
          do recenzji.
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-[12px] text-muted">Autor pracy</span>
          <input
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            maxLength={255}
            className={inputClass}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-[12px] text-muted">Kierunek</span>
          <input
            required
            value={fieldOfStudy}
            onChange={(e) => setFieldOfStudy(e.target.value)}
            maxLength={255}
            className={inputClass}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-[12px] text-muted">Typ pracy</span>
          <select
            value={thesisType}
            onChange={(e) => {
              typeChosen.current = true
              setThesisType(e.target.value as ThesisType)
              setGuidelineSetId("")
            }}
            className={inputClass}
          >
            <option value="bachelor">Licencjacka</option>
            <option value="master">Magisterska</option>
            <option value="master_article">Magisterska (artykuł)</option>
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-[12px] text-muted">Tytuł (opcjonalnie)</span>
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            className={inputClass}
          />
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
            className={inputClass}
          />
          <span className="mt-1 block text-[12px] text-muted">
            AI traktuje to jako kontekst, nie listę wymagań.
          </span>
        </label>
      </div>

      <p className="mt-3 text-[12.5px] text-muted">
        Tekst i plik pracy zostaną usunięte po 150 dniach. Wyniki AI zostają, dopóki sam ich nie
        usuniesz.
      </p>

      {error && (
        <p data-testid="review-form-error" className="mt-3 text-[13px] text-critical-text">
          {error}
        </p>
      )}

      <div className="mt-4 flex gap-2">
        <button
          type="submit"
          disabled={saving}
          className="h-9 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
        >
          {saving ? "Wczytywanie pracy…" : "Dalej"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="h-9 rounded-lg border border-line px-4 text-[13px] font-medium text-foreground hover:bg-surface-alt transition-colors"
        >
          Anuluj
        </button>
      </div>
    </form>
  )
}
