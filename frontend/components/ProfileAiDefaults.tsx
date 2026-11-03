"use client"

import { useState } from "react"
import ModelSelect, { useModelChoice } from "@/components/ai/ModelSelect"
import ReviewToneChoice from "@/components/ai/ReviewToneChoice"
import { useAiDefaults, writeAiDefaults, type AiDefaults } from "@/lib/aiDefaults"

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

  const { preference } = useModelChoice(draft.model)

  function save(): void {
    // Saving drops a provider whose key is gone, instead of keeping a
    // preference that can no longer be honoured.
    writeAiDefaults({ ...draft, model: preference })
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
        <ModelSelect
          value={draft.model}
          onChange={(model) => setDraft({ ...draft, model })}
          className={inputClass}
          labelClassName="mb-1 block text-[12px] text-muted"
        />
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
        <div>
          <ReviewToneChoice
            name="profile-review-tone"
            value={draft.reviewTone}
            onChange={(reviewTone) => setDraft({ ...draft, reviewTone })}
          />
          <p className="mt-1.5 text-[11.5px] text-muted">
            Dotyczy tylko akcji &bdquo;Recenzja finalna&rdquo;.
          </p>
        </div>
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
