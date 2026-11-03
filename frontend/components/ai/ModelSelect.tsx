"use client"

import Link from "next/link"
import useSWR from "swr"
import { fetcher } from "@/lib/api.client"
import type { ApiKeyStatus, ModelCatalog } from "@/lib/api.types"
import {
  byokValue,
  PROVIDER_LABELS,
  PROVIDERS,
  resolveModel,
  type Provider,
  type ResolvedModel,
} from "@/lib/modelChoice"

export interface ModelChoice extends ResolvedModel {
  /**
   * The choice worth saving: what was given, unless it named a key that is
   * gone — then what it fell back to.
   */
  preference: string
  catalog: ModelCatalog | undefined
  /** Providers the promoter has a key for, in display order. */
  keys: Provider[]
}

/**
 * What to actually send, given a saved choice (see `lib/modelChoice`).
 */
export function useModelChoice(value: string): ModelChoice {
  const { data: catalog } = useSWR<ModelCatalog>("/api/models", fetcher)
  const { data: status } = useSWR<ApiKeyStatus>("/api/settings/api-key/status", fetcher)
  const resolved = resolveModel(value, status?.providers)
  return {
    ...resolved,
    preference: resolved.missingKey ? resolved.selected : value,
    catalog,
    keys: PROVIDERS.filter((p) => status?.providers?.includes(p)),
  }
}

interface ModelSelectProps {
  /** A saved choice — see `lib/modelChoice` for what the string can hold. */
  value: string
  onChange: (value: string) => void
  className: string
  labelClassName: string
}

/** Picks which of the promoter's own provider keys an action runs on. */
export default function ModelSelect({
  value,
  onChange,
  className,
  labelClassName,
}: ModelSelectProps) {
  const { selected, provider, missingKey, needsKey, catalog, keys } = useModelChoice(value)

  return (
    <label className="block">
      <span className={labelClassName}>Model</span>
      <select
        value={selected}
        onChange={(e) => onChange(e.target.value)}
        className={className}
        data-testid="model-select"
      >
        {keys.length === 0 ? (
          <option value="">Brak klucza API</option>
        ) : (
          <>
            {selected === "" && <option value="">Wybierz klucz API</option>}
            {keys.map((p) => (
              <option key={p} value={byokValue(p)}>
                {PROVIDER_LABELS[p]}
                {catalog?.byok[p] ? ` · ${catalog.byok[p]}` : ""}
              </option>
            ))}
          </>
        )}
      </select>
      {provider && (
        <span data-testid="model-byok" className="mt-1 block text-[11.5px] text-muted">
          Akcja pójdzie na Twoje konto u dostawcy.
        </span>
      )}
      {needsKey && (
        <span data-testid="model-needs-key" className="mt-1 block text-[11.5px] text-major-text">
          {missingKey
            ? `Klucz ${PROVIDER_LABELS[missingKey]} z Twoich ustawień został usunięty. `
            : "Akcje działają na Twoim kluczu API do Claude albo OpenAI. "}
          <Link href="/profile" className="underline">
            Dodaj klucz w profilu
          </Link>
          .
        </span>
      )}
    </label>
  )
}
