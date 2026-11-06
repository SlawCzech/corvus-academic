"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import { acceptTerms } from "@/lib/api.client"

interface AcceptTermsFormProps {
  version: string
  next: string
}

export default function AcceptTermsForm({ version, next }: AcceptTermsFormProps) {
  const router = useRouter()
  const [agreed, setAgreed] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await acceptTerms(version)
      router.replace(next)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać akceptacji")
      setSaving(false)
    }
  }

  return (
    <form
      onSubmit={submit}
      data-testid="accept-terms"
      className="sticky bottom-0 mt-10 rounded-xl border border-line bg-surface p-5 shadow-sm"
    >
      <label className="flex items-start gap-3 text-[13.5px] leading-relaxed text-foreground">
        <input
          type="checkbox"
          checked={agreed}
          onChange={(e) => setAgreed(e.target.checked)}
          className="mt-1"
        />
        <span>
          Akceptuję regulamin, w tym umowę powierzenia przetwarzania danych (§ 5), i oświadczam, że
          mam podstawę prawną do wprowadzania danych moich studentów do Corvusa.
        </span>
      </label>
      {error && (
        <p data-testid="accept-terms-error" className="mt-3 text-[13px] text-critical-text">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={!agreed || saving}
        className="mt-4 h-9 rounded-lg bg-accent px-4 text-[13px] font-medium text-white transition-colors hover:bg-accent-hover disabled:cursor-default disabled:opacity-50"
      >
        {saving ? "Zapisuję…" : "Akceptuję"}
      </button>
    </form>
  )
}
