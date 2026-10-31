"use client"

import { useState } from "react"
import ModelSelect, { useModelChoice } from "@/components/ai/ModelSelect"
import FileUpload from "@/components/FileUpload"
import { triggerAction, uploadFragment } from "@/lib/api.client"
import type { PartEntry } from "@/lib/api.types"
import { useAiDefaults } from "@/lib/aiDefaults"

const inputClass =
  "w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[13.5px] " +
  "text-foreground focus:border-accent focus:outline-none"
const labelClass = "mb-1 block text-[12.5px] font-medium text-muted-strong"

function today(): string {
  return new Date().toLocaleDateString("sv-SE")
}

/**
 * Enter what a student sent. Two requests on purpose: the fragment is saved
 * first, so a run that cannot start — no key, the agent down — never loses
 * it, and the card on the timeline can start it again.
 */
export default function FragmentUploadForm({
  studentId,
  parts,
  onSaved,
  onClose,
}: {
  studentId: string
  parts: PartEntry[]
  onSaved: () => void
  onClose: () => void
}) {
  const defaults = useAiDefaults()
  // Remounts once the real defaults are known, as `ActionPanel` does.
  return (
    <Form
      key={`${defaults.model}:${defaults.language}`}
      studentId={studentId}
      parts={parts}
      initialModel={defaults.model}
      language={defaults.language}
      onSaved={onSaved}
      onClose={onClose}
    />
  )
}

function Form({
  studentId,
  parts,
  initialModel,
  language,
  onSaved,
  onClose,
}: {
  studentId: string
  parts: PartEntry[]
  initialModel: string
  language: string
  onSaved: () => void
  onClose: () => void
}) {
  const [partName, setPartName] = useState("")
  const [source, setSource] = useState<"file" | "text">("file")
  const [file, setFile] = useState<File | null>(null)
  const [text, setText] = useState("")
  const [receivedOn, setReceivedOn] = useState(today())
  const [question, setQuestion] = useState("")
  const [withAi, setWithAi] = useState(true)
  const [model, setModel] = useState(initialModel)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { provider, model: effectiveModel, needsKey } = useModelChoice(model)

  const ready =
    partName.trim() !== "" && (source === "file" ? file !== null : text.trim() !== "")

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    if (!ready) return
    setBusy(true)
    setError(null)
    try {
      const fragment = await uploadFragment(studentId, {
        partName: partName.trim(),
        file: source === "file" ? file : null,
        text: source === "text" ? text : null,
        receivedOn,
        question: question.trim() || null,
      })
      if (withAi && !needsKey) {
        try {
          await triggerAction(studentId, "review_fragment", undefined, {
            provider,
            model: effectiveModel,
            language,
            fragmentId: fragment.id,
          })
        } catch {
          // The card says the fragment has no summary and offers to try again.
        }
      }
      onSaved()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać fragmentu")
    } finally {
      setBusy(false)
    }
  }

  return (
    <form
      onSubmit={(event) => void submit(event)}
      data-testid="fragment-form"
      className="mb-6 rounded-xl border border-line bg-surface p-5"
    >
      <div className="mb-4 grid grid-cols-2 gap-4">
        <label className="block">
          <span className={labelClass}>Część pracy</span>
          <input
            list="thesis-parts"
            value={partName}
            onChange={(e) => setPartName(e.target.value)}
            placeholder="np. Rozdział 2: metodologia"
            maxLength={255}
            className={inputClass}
          />
          <datalist id="thesis-parts">
            {parts.map((p) => (
              <option key={p.id} value={p.name} />
            ))}
          </datalist>
        </label>
        <label className="block">
          <span className={labelClass}>Kiedy student to przysłał</span>
          <input
            type="date"
            value={receivedOn}
            max={today()}
            onChange={(e) => setReceivedOn(e.target.value)}
            className={inputClass}
          />
        </label>
      </div>

      <div className="mb-2 flex gap-3 text-[12.5px]">
        <button
          type="button"
          onClick={() => setSource("file")}
          className={source === "file" ? "font-semibold text-accent" : "text-muted"}
        >
          Plik
        </button>
        <button
          type="button"
          onClick={() => setSource("text")}
          className={source === "text" ? "font-semibold text-accent" : "text-muted"}
        >
          Wklej tekst
        </button>
      </div>
      <div className="mb-4">
        {source === "file" ? (
          <FileUpload
            onFileSelect={setFile}
            disabled={busy}
            prompt="Upuść tu plik z fragmentem albo kliknij"
          />
        ) : (
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={6}
            aria-label="Tekst fragmentu"
            placeholder="Wklej tekst z maila"
            className={inputClass}
          />
        )}
      </div>

      <label className="mb-4 block">
        <span className={labelClass}>Pytanie do AI (opcjonalnie)</span>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={4000}
          placeholder="np. Czy literatura wystarcza do tego tematu?"
          className={inputClass}
        />
      </label>

      <label className="mb-3 flex items-center gap-2 text-[13px] text-foreground">
        <input
          type="checkbox"
          checked={withAi}
          onChange={(e) => setWithAi(e.target.checked)}
        />
        Podsumuj i przygotuj szkic feedbacku
      </label>
      {withAi && (
        <div className="mb-4 max-w-sm">
          <ModelSelect
            value={model}
            onChange={setModel}
            className={inputClass}
            labelClassName={labelClass}
          />
          {needsKey && (
            <p className="mt-1 text-[12.5px] text-muted">
              Bez klucza API fragment zapisze się bez podsumowania.
            </p>
          )}
        </div>
      )}

      {error && (
        <p role="alert" className="mb-3 text-[13px] text-critical-text">
          {error}
        </p>
      )}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={!ready || busy}
          className="h-9 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {busy ? "Zapisuję…" : "Zapisz fragment"}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="h-9 rounded-lg border border-line px-4 text-[13px] font-medium text-foreground hover:bg-surface-alt"
        >
          Anuluj
        </button>
      </div>
    </form>
  )
}
