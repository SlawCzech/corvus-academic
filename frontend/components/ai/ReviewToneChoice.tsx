"use client"

import { REVIEW_TONES } from "@/components/ai/reviewTones"

interface ReviewToneChoiceProps {
  value: string
  onChange: (value: string) => void
  /** Radio group name — unique per form on the page. */
  name: string
}

/**
 * Automatic by default; picking "set it yourself" lays the six tones out as
 * radios with what each one means — a dropdown hid exactly that.
 */
export default function ReviewToneChoice({ value, onChange, name }: ReviewToneChoiceProps) {
  const manual = value !== "auto"

  return (
    <fieldset>
      <legend className="mb-1.5 text-[11.5px] text-muted">Ton recenzji</legend>

      <div role="radiogroup" className="flex gap-1 rounded-lg bg-surface-alt p-1">
        {[
          { key: false, label: "Automatyczny" },
          { key: true, label: "Wybieram sam" },
        ].map((opt) => (
          <button
            key={String(opt.key)}
            type="button"
            role="radio"
            aria-checked={manual === opt.key}
            onClick={() => onChange(opt.key ? (manual ? value : "positive") : "auto")}
            className={`h-8 flex-1 rounded-md px-3 text-[13px] font-medium transition-colors ${
              manual === opt.key
                ? "bg-surface text-foreground shadow-sm"
                : "text-muted-strong hover:text-foreground"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {!manual && (
        <p className="mt-1.5 text-[12px] text-muted">
          Model dobiera ton na podstawie analizy pracy.
        </p>
      )}

      {manual && (
        <div className="mt-2 grid grid-cols-2 gap-2">
          {REVIEW_TONES.map((t) => {
            const checked = value === t.value
            return (
              <label
                key={t.value}
                className={`flex cursor-pointer items-start gap-2.5 rounded-lg border px-3 py-2 transition-colors ${
                  checked
                    ? "border-accent bg-accent-soft"
                    : "border-line bg-surface hover:border-muted"
                }`}
              >
                <input
                  type="radio"
                  name={name}
                  value={t.value}
                  checked={checked}
                  onChange={() => onChange(t.value)}
                  className="mt-0.5 accent-[var(--accent)]"
                />
                <span>
                  <span className="block text-[13px] font-medium text-foreground">
                    {t.label}
                  </span>
                  <span className="block text-[12px] text-muted">{t.description}</span>
                </span>
              </label>
            )
          })}
        </div>
      )}
    </fieldset>
  )
}
