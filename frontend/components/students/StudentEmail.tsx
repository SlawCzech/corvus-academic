"use client"

import { useState } from "react"

function CopyButton({ text, label }: { text: string; label: string }) {
  const [notice, setNotice] = useState<string | null>(null)

  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(text)
      setNotice("Skopiowano")
    } catch {
      setNotice("Schowek jest niedostępny, skopiuj tekst ręcznie.")
    }
  }

  return (
    <span className="flex items-center gap-2">
      <button
        type="button"
        disabled={!text}
        onClick={() => void copy()}
        className="h-8 rounded-lg border border-line px-3 text-[12.5px] font-medium text-foreground hover:bg-surface-alt disabled:opacity-50"
      >
        {label}
      </button>
      {notice && <span className="text-[12.5px] text-muted">{notice}</span>}
    </span>
  )
}

/** A draft to read and paste into the promoter's own mail. Corvus sends nothing. */
export default function StudentEmail({ subject, body }: { subject: string; body: string }) {
  return (
    <div data-testid="student-email">
      <p className="text-[13px] font-semibold text-foreground">Temat: {subject}</p>
      <p className="mt-3 whitespace-pre-wrap text-[13px] text-muted-strong">{body}</p>
      <p className="mt-3 text-[12.5px] text-muted">
        To szkic. Przeczytaj go przed wysłaniem i dopisz swój podpis.
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <CopyButton text={body} label="Kopiuj treść" />
        <CopyButton text={subject} label="Kopiuj temat" />
      </div>
    </div>
  )
}
