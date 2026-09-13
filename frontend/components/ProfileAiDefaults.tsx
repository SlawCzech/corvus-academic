"use client"

import { useState } from "react"
import { useAiDefaults, writeAiDefaults, type AiDefaults } from "@/lib/aiDefaults"

const TONE_OPTIONS: { value: string; label: string }[] = [
  { value: "auto", label: "Automatyczny" },
  { value: "enthusiastic", label: "Entuzjastyczny" },
  { value: "commendable", label: "Pochlebny" },
  { value: "positive", label: "Pozytywny" },
  { value: "diplomatic", label: "Dyplomatyczny" },
  { value: "reserved", label: "Powściągliwy" },
  { value: "negative", label: "Negatywny" },
]

const inputClass =
  "w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[14px] " +
  "text-foreground focus:border-accent focus:outline-none"

export default function ProfileAiDefaults() {
  const saved = useAiDefaults()
  // Remounts once the real (possibly non-fallback) saved value is known, so
  // the draft below starts from it without an effect.
  return (
    <ProfileAiDefaultsForm
      key={`${saved.model}:${saved.language}:${saved.reviewTone}`}
      saved={saved}
    />
  )
}

function ProfileAiDefaultsForm({ saved }: { saved: AiDefaults }) {
  const [draft, setDraft] = useState<AiDefaults>(saved)
  const [justSaved, setJustSaved] = useState(false)

  function save(): void {
    writeAiDefaults(draft)
    setJustSaved(true)
    setTimeout(() => setJustSaved(false), 2000)
  }

  return (
    <section data-testid="ai-defaults-section" className="rounded-xl border border-line bg-surface p-5">
      <p className="mb-4 text-[13px] text-muted">
        Wypełniają opcje przy uruchamianiu akcji — możesz je nadpisać za
        każdym razem przy konkretnym studencie. Zapisane tylko w tej
        przeglądarce.
      </p>

      <div className="flex flex-col gap-3">
        <label className="block">
          <span className="mb-1 block text-[12px] text-muted">
            Model (opcjonalnie — tag Ollama, np. qwen3:30b-a3b)
          </span>
          <input
            value={draft.model}
            onChange={(e) => setDraft({ ...draft, model: e.target.value })}
            placeholder="zostaw puste dla domyślnego"
            className={inputClass}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-[12px] text-muted">Język</span>
          <select
            value={draft.language}
            onChange={(e) => setDraft({ ...draft, language: e.target.value })}
            className={inputClass}
          >
            <option value="pl">Polski</option>
            <option value="en">English</option>
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-[12px] text-muted">
            Ton recenzji (dotyczy tylko akcji &bdquo;Napisz recenzję&rdquo;)
          </span>
          <select
            value={draft.reviewTone}
            onChange={(e) => setDraft({ ...draft, reviewTone: e.target.value })}
            className={inputClass}
          >
            {TONE_OPTIONS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={save}
          className="h-9 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors"
        >
          Zapisz ustawienia
        </button>
        {justSaved && <span className="text-[13px] text-muted">Zapisano</span>}
      </div>
    </section>
  )
}
