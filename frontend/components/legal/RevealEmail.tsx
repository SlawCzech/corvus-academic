"use client"

import { useState } from "react"

import { revealEmail } from "@/components/legal/hiddenEmail"

/** The operator's address behind a button; see `hiddenEmail.ts` for why. */
export default function RevealEmail({ hidden }: { hidden: string }) {
  const [email, setEmail] = useState<string | null>(null)

  if (email === null) {
    return (
      <button
        type="button"
        onClick={() => setEmail(revealEmail(hidden))}
        className="text-accent underline underline-offset-4 hover:text-accent-hover"
      >
        pokaż adres e-mail
      </button>
    )
  }
  return (
    <a href={`mailto:${email}`} className="text-accent underline underline-offset-4">
      {email}
    </a>
  )
}
