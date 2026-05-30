"use client"

import { useState } from "react"

type ModelBackend = "local" | "cloud"
type Provider = "claude" | "openai"
type SaveStatus = "idle" | "saving" | "saved" | "error"

export default function AdminApiKeySection() {
  const [backend, setBackend] = useState<ModelBackend>("local")
  const [provider, setProvider] = useState<Provider>("claude")
  const [apiKey, setApiKey] = useState("")
  const [showKey, setShowKey] = useState(false)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle")

  const handleSave = async (): Promise<void> => {
    if (backend === "local") return
    setSaveStatus("saving")
    const res = await fetch("/api/admin/api-key", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: apiKey, provider }),
    })
    setSaveStatus(res.ok ? "saved" : "error")
  }

  return (
    <section data-testid="ai-model-section">
      <h2 className="mb-4 text-lg font-semibold text-gray-900">AI Model</h2>

      <fieldset className="mb-4">
        <legend className="mb-2 text-sm font-medium text-gray-700">
          Backend
        </legend>
        <div className="space-y-2">
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="radio"
              name="backend"
              value="local"
              checked={backend === "local"}
              onChange={() => setBackend("local")}
              data-testid="radio-local"
            />
            <span>LOCAL (Ollama)</span>
          </label>
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="radio"
              name="backend"
              value="cloud"
              checked={backend === "cloud"}
              onChange={() => setBackend("cloud")}
              data-testid="radio-cloud"
            />
            <span>CLOUD (API)</span>
          </label>
        </div>
      </fieldset>

      {backend === "cloud" && (
        <div className="mb-4 space-y-3" data-testid="cloud-settings">
          <div>
            <label
              htmlFor="provider"
              className="block text-sm font-medium text-gray-700"
            >
              Provider
            </label>
            <select
              id="provider"
              value={provider}
              onChange={(e) => setProvider(e.target.value as Provider)}
              data-testid="provider-select"
              className="mt-1 block rounded-md border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="claude">Claude (Anthropic)</option>
              <option value="openai">OpenAI</option>
            </select>
          </div>

          <div>
            <label
              htmlFor="api-key"
              className="block text-sm font-medium text-gray-700"
            >
              API Key
            </label>
            <div className="mt-1 flex gap-2">
              <input
                id="api-key"
                type={showKey ? "text" : "password"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                data-testid="api-key-input"
                placeholder="sk-…"
                className="block flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setShowKey((v) => !v)}
                data-testid="toggle-visibility"
                aria-label={showKey ? "Hide API key" : "Show API key"}
                className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-600 hover:bg-gray-50"
              >
                {showKey ? "Hide" : "Show"}
              </button>
            </div>
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={handleSave}
        disabled={backend === "local" || saveStatus === "saving"}
        data-testid="save-api-key"
        className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
      >
        {saveStatus === "saving" ? "Saving…" : "Save"}
      </button>

      {saveStatus === "saved" && (
        <p
          role="status"
          data-testid="save-success"
          className="mt-2 text-sm text-green-700"
        >
          Saved successfully.
        </p>
      )}
      {saveStatus === "error" && (
        <p
          role="alert"
          data-testid="save-error"
          className="mt-2 text-sm text-red-700"
        >
          Failed to save API key.
        </p>
      )}
    </section>
  )
}
