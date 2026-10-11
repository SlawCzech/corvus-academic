"use client"

import { useState } from "react"
import useSWR from "swr"
import { fetcher } from "@/lib/api.client"
import type { ApiKeySaved, ApiKeyStatus, ModelCatalog } from "@/lib/api.types"
import { PROVIDER_LABELS, PROVIDERS, type Provider } from "@/lib/modelChoice"

// "rejected": the provider refused the key, so it was not stored.
// "unverified": stored, but the provider could not be asked (offline, down).
type SaveStatus = "idle" | "saving" | "saved" | "unverified" | "rejected" | "error"

const STATUS_KEY = "/api/settings/api-key/status"

/**
 * The promoter's own provider keys — one per provider.
 *
 * A stored key is used only for the actions the promoter runs on it; which
 * one, if any, is picked per action. Keys are stored encrypted and never
 * sent back.
 */
export default function ApiKeySection() {
  const { data: status, mutate } = useSWR<ApiKeyStatus>(STATUS_KEY, fetcher)
  const { data: catalog } = useSWR<ModelCatalog>("/api/models", fetcher)
  // A server without local models (ADR 0013): a key is what actions run on.
  const keysOnly = catalog?.local_enabled === false
  const [provider, setProvider] = useState<Provider>("claude")
  const [apiKey, setApiKey] = useState("")
  const [showKey, setShowKey] = useState(false)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle")
  // What the provider itself said about a key it refused, when it said anything.
  const [providerMessage, setProviderMessage] = useState<string | null>(null)

  async function save(): Promise<void> {
    if (!apiKey.trim()) return
    setSaveStatus("saving")
    setProviderMessage(null)
    const res = await fetch("/api/settings/api-key", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: apiKey, provider }),
    })
    if (!res.ok) {
      if (res.status === 422) {
        const refusal = (await res.json().catch(() => null)) as {
          provider_message?: string | null
        } | null
        setProviderMessage(refusal?.provider_message ?? null)
      }
      setSaveStatus(res.status === 422 ? "rejected" : "error")
      return
    }
    const saved = (await res.json()) as Partial<ApiKeySaved>
    setSaveStatus(saved.verified === false ? "unverified" : "saved")
    setApiKey("")
    void mutate()
  }

  async function remove(which: Provider): Promise<void> {
    setSaveStatus("saving")
    const res = await fetch(`/api/settings/api-key/${which}`, { method: "DELETE" })
    setSaveStatus(res.ok ? "idle" : "error")
    if (res.ok) void mutate()
  }

  const stored = PROVIDERS.filter((p) => status?.providers?.includes(p))
  const replacing = stored.includes(provider)

  return (
    <section data-testid="api-key-section">
      <p className="mb-4 text-[13px] text-muted">
        Możesz zapisać po jednym kluczu dla każdego dostawcy.{" "}
        {keysOnly
          ? "Akcje AI działają wyłącznie na Twoim kluczu — przy każdej wybierasz, na którym."
          : "Przy każdej akcji wybierasz, czy idzie na któryś z nich, czy na model uruchomiony lokalnie."}{" "}
        Klucze są przechowywane zaszyfrowane i nigdy nie wracają w odpowiedzi.
      </p>

      <div data-testid="api-key-status" className="mb-4 text-[13px]">
        {stored.length === 0 ? (
          <span className={keysOnly ? "text-major-text" : "text-muted"}>
            {keysOnly
              ? "Brak kluczy — dodaj klucz, żeby uruchamiać akcje AI"
              : "Brak kluczy — akcje idą na model lokalny"}
          </span>
        ) : (
          <ul className="space-y-1.5">
            {stored.map((p) => (
              <li key={p} data-testid={`stored-key-${p}`} className="flex items-center gap-3">
                <span className="text-foreground">Klucz zapisany — {PROVIDER_LABELS[p]}</span>
                <button
                  type="button"
                  onClick={() => void remove(p)}
                  data-testid={`remove-api-key-${p}`}
                  className="rounded-lg border border-line px-2.5 py-1 text-[12px] text-muted-strong hover:bg-surface-alt transition-colors"
                >
                  Usuń
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="space-y-3">
        <label className="block">
          <span className="mb-1 block text-[12px] text-muted">Dostawca</span>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as Provider)}
            data-testid="provider-select"
            className="rounded-lg border border-line bg-surface px-3 py-1.5 text-[14px] text-foreground"
          >
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>
                {PROVIDER_LABELS[p]}
              </option>
            ))}
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
          {saveStatus === "saving"
            ? "Zapisywanie…"
            : replacing
              ? "Zastąp klucz"
              : "Zapisz klucz"}
        </button>

        {saveStatus === "saved" && (
          <span data-testid="save-ok" className="text-[13px] text-muted">
            Zapisano — dostawca przyjął klucz
          </span>
        )}
        {saveStatus === "unverified" && (
          <span data-testid="save-unverified" className="text-[13px] text-major-text">
            Zapisano, ale dostawca nie odpowiedział, więc klucz nie został sprawdzony
          </span>
        )}
        {saveStatus === "rejected" && (
          <span data-testid="save-rejected" className="text-[13px] text-critical-text">
            Dostawca odrzucił ten klucz, więc nie został zapisany.{" "}
            {providerMessage ? (
              <>
                Odpowiedź dostawcy:{" "}
                <span data-testid="provider-message">„{providerMessage}”</span>
              </>
            ) : (
              "Sprawdź, czy klucz został skopiowany w całości."
            )}
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
