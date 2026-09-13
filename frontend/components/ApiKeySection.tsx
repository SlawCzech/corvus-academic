"use client"

import { useState } from "react"
import useSWR from "swr"
import { fetcher } from "@/lib/api.client"

type Provider = "claude" | "openai"
type SaveStatus = "idle" | "saving" | "saved" | "error"

interface ApiKeyStatus {
  configured: boolean
  provider: string | null
}

const PROVIDER_LABELS: Record<string, string> = {
  claude: "Claude (Anthropic)",
  openai: "OpenAI",
}

const STATUS_KEY = "/api/settings/api-key/status"

/**
 * The promoter's own provider key.
 *
 * Set one and your actions run on your account; leave it empty and they run
 * on the self-hosted model. The key is stored encrypted and never sent back.
 */
export default function ApiKeySection() {
  const { data: status, mutate } = useSWR<ApiKeyStatus>(STATUS_KEY, fetcher)
  const [provider, setProvider] = useState<Provider>("claude")
  const [apiKey, setApiKey] = useState("")
  const [showKey, setShowKey] = useState(false)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle")

  async function save(): Promise<void> {
    if (!apiKey.trim()) return
    setSaveStatus("saving")
    const res = await fetch("/api/settings/api-key", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: apiKey, provider }),
    })
    setSaveStatus(res.ok ? "saved" : "error")
    if (res.ok) {
      setApiKey("")
      void mutate()
    }
  }

  async function remove(): Promise<void> {
    setSaveStatus("saving")
    const res = await fetch("/api/settings/api-key", { method: "DELETE" })
    setSaveStatus(res.ok ? "idle" : "error")
    if (res.ok) void mutate()
  }

  return (
    <section data-testid="api-key-section">
      <p className="mb-4 text-[13px] text-muted">
        Bez własnego klucza akcje AI liczą się na modelu uruchomionym lokalnie.
        Klucz jest przechowywany zaszyfrowany i nigdy nie wraca w odpowiedzi.
      </p>

      <p data-testid="api-key-status" className="mb-4 text-[13px]">
        {status?.configured ? (
          <span className="text-foreground">
            Klucz zapisany
            {status.provider
              ? ` — ${PROVIDER_LABELS[status.provider] ?? status.provider}`
              : ""}
          </span>
        ) : (
          <span className="text-muted">Brak klucza — model lokalny</span>
        )}
      </p>

      <div className="space-y-3">
        <label className="block">
          <span className="mb-1 block text-[12px] text-muted">Dostawca</span>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as Provider)}
            data-testid="provider-select"
            className="rounded-lg border border-line bg-surface px-3 py-1.5 text-[14px] text-foreground"
          >
            <option value="claude">Claude (Anthropic)</option>
            <option value="openai">OpenAI</option>
          </select>
        </label>

        <label className="block">
          <span className="mb-1 block text-[12px] text-muted">Klucz API</span>
          <span className="flex gap-2">
            <input
              type={showKey ? "text" : "password"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              data-testid="api-key-input"
              placeholder="sk-…"
              className="flex-1 rounded-lg border border-line bg-surface px-3 py-1.5 font-mono text-[13px] text-foreground focus:border-accent focus:outline-none"
            />
            <button
              type="button"
              onClick={() => setShowKey((v) => !v)}
              data-testid="toggle-visibility"
              aria-label={showKey ? "Ukryj klucz" : "Pokaż klucz"}
              className="rounded-lg border border-line px-3 text-[13px] text-muted-strong hover:bg-surface-alt transition-colors"
            >
              {showKey ? "Ukryj" : "Pokaż"}
            </button>
          </span>
        </label>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={() => void save()}
          disabled={saveStatus === "saving" || !apiKey.trim()}
          data-testid="save-api-key"
          className="h-9 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors disabled:opacity-40"
        >
          {saveStatus === "saving" ? "Zapisywanie…" : "Zapisz klucz"}
        </button>

        {status?.configured && (
          <button
            type="button"
            onClick={() => void remove()}
            data-testid="remove-api-key"
            className="h-9 rounded-lg border border-line px-4 text-[13px] text-muted-strong hover:bg-surface-alt transition-colors"
          >
            Usuń klucz
          </button>
        )}

        {saveStatus === "saved" && (
          <span data-testid="save-ok" className="text-[13px] text-muted">
            Zapisano
          </span>
        )}
        {saveStatus === "error" && (
          <span data-testid="save-error" className="text-[13px] text-critical-text">
            Nie udało się zapisać klucza
          </span>
        )}
      </div>
    </section>
  )
}
