"use client"

import useSWR from "swr"
import { fetcher } from "@/lib/api.client"
import type { ApiKeyStatus, ModelCatalog } from "@/lib/api.types"

const PROVIDER_LABELS: Record<string, string> = {
  claude: "Claude",
  openai: "OpenAI",
}

/**
 * The model to actually send, given a saved preference.
 *
 * A preference can outlive its model — the admin withdraws it, or it is
 * removed from the server. Sending it anyway would only get the action
 * refused, so it falls back to the default ("") and says which model it was.
 */
export function useAvailableModel(value: string): {
  effective: string
  withdrawn: string | null
  catalog: ModelCatalog | undefined
  error: unknown
} {
  const { data: catalog, error } = useSWR<ModelCatalog>("/api/models", fetcher)
  if (!value || !catalog) return { effective: value, withdrawn: null, catalog, error }
  if (value === catalog.default) return { effective: "", withdrawn: null, catalog, error }
  if (catalog.available.some((m) => m.name === value)) {
    return { effective: value, withdrawn: null, catalog, error }
  }
  return { effective: "", withdrawn: value, catalog, error }
}

interface ModelSelectProps {
  /** A model tag, or "" for the default. */
  value: string
  onChange: (value: string) => void
  className: string
  labelClassName: string
}

/**
 * Picks the model an action runs on, from what the admin has made available.
 *
 * With a stored provider key the choice is not the promoter's to make here —
 * the run goes to that provider's model — so the picker says so instead of
 * offering local models that would be ignored.
 */
export default function ModelSelect({
  value,
  onChange,
  className,
  labelClassName,
}: ModelSelectProps) {
  const { effective, withdrawn, catalog, error } = useAvailableModel(value)
  const { data: key } = useSWR<ApiKeyStatus>("/api/settings/api-key/status", fetcher)

  if (key?.configured && key.provider) {
    const model = catalog?.byok[key.provider]
    return (
      <div className="block">
        <span className={labelClassName}>Model</span>
        <p data-testid="model-byok" className={`${className} bg-surface-alt text-muted-strong`}>
          {PROVIDER_LABELS[key.provider] ?? key.provider}
          {model ? ` · ${model}` : ""}
          <span className="text-muted"> — Twój klucz API</span>
        </p>
      </div>
    )
  }

  const unreachable = error !== undefined || catalog?.local_available === false

  return (
    <label className="block">
      <span className={labelClassName}>Model</span>
      <select
        value={effective}
        onChange={(e) => onChange(e.target.value)}
        className={className}
        data-testid="model-select"
      >
        <option value="">Domyślny{catalog ? ` (${catalog.default})` : ""}</option>
        {(catalog?.available ?? [])
          .filter((m) => m.name !== catalog?.default)
          .map((m) => (
            <option key={m.name} value={m.name}>
              {m.name}
              {m.parameter_size ? ` · ${m.parameter_size}` : ""}
            </option>
          ))}
      </select>
      {withdrawn && (
        <span data-testid="model-withdrawn" className="mt-1 block text-[11.5px] text-major-text">
          Model {withdrawn} z Twoich ustawień nie jest już dostępny — używam
          domyślnego.
        </span>
      )}
      {unreachable && (
        <span className="mt-1 block text-[11.5px] text-muted">
          Nie udało się pobrać listy modeli — zostaje domyślny.
        </span>
      )}
    </label>
  )
}
