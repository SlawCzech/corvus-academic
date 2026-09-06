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
      <p className="mb-4 text-[13px] text-gray-500">
        Bez własnego klucza akcje AI liczą się na modelu uruchomionym lokalnie.
        Klucz jest przechowywany zaszyfrowany i nigdy nie wraca w odpowiedzi.
      </p>

      <p data-testid="api-key-status" className="mb-4 text-[13px]">
        {status?.configured ? (
          <span className="text-gray-900 dark:text-gray-100">
            Klucz zapisany
            {status.provider
              ? ` — ${PROVIDER_LABELS[status.provider] ?? status.provider}`
              : ""}
          </span>
        ) : (
          <span className="text-gray-500">Brak klucza — model lokalny</span>
        )}
      </p>

      <div className="space-y-3">
        <label className="block">
          <span className="mb-1 block text-[12px] text-gray-500">Dostawca</span>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as Provider)}
            data-testid="provider-select"
            className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-[14px] text-gray-900 dark:text-gray-100"
          >
            <option value="claude">Claude (Anthropic)</option>
            <option value="openai">OpenAI</option>
          </select>
        </label>

        <label className="block">
          <span className="mb-1 block text-[12px] text-gray-500">Klucz API</span>
          <span className="flex gap-2">
            <input
              type={showKey ? "text" : "password"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              data-testid="api-key-input"
              placeholder="sk-…"
              className="flex-1 rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 font-mono text-[13px] text-gray-900 dark:text-gray-100 focus:border-gray-900 dark:focus:border-gray-300 focus:outline-none"
            />
            <button
              type="button"
              onClick={() => setShowKey((v) => !v)}
              data-testid="toggle-visibility"
              aria-label={showKey ? "Ukryj klucz" : "Pokaż klucz"}
              className="rounded-md border border-gray-300 dark:border-gray-700 px-3 text-[13px] text-gray-600 dark:text-gray-400"
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
          className="h-8 rounded-md bg-gray-900 dark:bg-white px-4 text-[13px] font-medium text-white dark:text-gray-900 disabled:opacity-40"
        >
          {saveStatus === "saving" ? "Zapisywanie…" : "Zapisz klucz"}
        </button>

        {status?.configured && (
          <button
            type="button"
            onClick={() => void remove()}
            data-testid="remove-api-key"
            className="h-8 rounded-md border border-gray-300 dark:border-gray-700 px-4 text-[13px] text-gray-700 dark:text-gray-300"
          >
            Usuń klucz
          </button>
        )}

        {saveStatus === "saved" && (
          <span data-testid="save-ok" className="text-[13px] text-gray-500">
            Zapisano
          </span>
        )}
        {saveStatus === "error" && (
          <span data-testid="save-error" className="text-[13px] text-red-600">
            Nie udało się zapisać klucza
          </span>
        )}
      </div>
    </section>
  )
}
