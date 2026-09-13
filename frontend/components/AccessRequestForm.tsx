"use client"

import { useState } from "react"

export default function AccessRequestForm() {
  const [email, setEmail] = useState("")
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle")

  async function onSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    setStatus("sending")
    try {
      const res = await fetch("/api/access-requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      })
      setStatus(res.ok ? "sent" : "error")
    } catch {
      setStatus("error")
    }
  }

  if (status === "sent") {
    return (
      <div>
        <h1 className="text-[24px] font-semibold text-foreground">Prośba wysłana</h1>
        <p className="mt-3 text-[13.5px] leading-relaxed text-muted-strong">
          Administrator zobaczy Twój adres email i skontaktuje się, gdy
          założy konto.
        </p>
      </div>
    )
  }

  return (
    <form onSubmit={(e) => void onSubmit(e)} data-testid="access-request-form">
      <h1 className="mb-1.5 text-[24px] font-semibold text-foreground">
        Poproś o dostęp
      </h1>
      <p className="mb-7 text-[13.5px] text-muted">
        Konta zakłada administrator uczelni. Zostaw email, a się z Tobą
        skontaktuje.
      </p>

      <label className="mb-6 block">
        <span className="mb-1.5 block text-[13px] font-medium text-muted-strong">
          Email uczelniany
        </span>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="jan.kowalski@uczelnia.edu.pl"
          data-testid="access-request-email"
          className="h-[42px] w-full rounded-lg border border-line bg-surface px-3.5 text-[14px] text-foreground focus:border-accent focus:outline-none"
        />
      </label>

      {status === "error" && (
        <p
          role="alert"
          data-testid="access-request-error"
          className="mb-4 text-[13px] text-critical-text"
        >
          Nie udało się wysłać prośby. Spróbuj ponownie.
        </p>
      )}

      <button
        type="submit"
        disabled={status === "sending"}
        data-testid="access-request-submit"
        className="h-11 w-full rounded-lg bg-accent text-[14px] font-semibold text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
      >
        {status === "sending" ? "Wysyłanie…" : "Wyślij prośbę"}
      </button>
    </form>
  )
}
