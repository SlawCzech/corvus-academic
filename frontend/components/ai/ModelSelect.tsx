"use client"

import Link from "next/link"
import useSWR from "swr"
import { fetcher } from "@/lib/api.client"
import type { ApiKeyStatus, ModelCatalog } from "@/lib/api.types"
import {
  byokValue,
  LOCAL_DEFAULT,
  PROVIDER_LABELS,
  PROVIDERS,
  resolveModel,
  type Provider,
  type ResolvedModel,
} from "@/lib/modelChoice"

export interface ModelChoice extends ResolvedModel {
  /**
   * The choice worth saving: what was given, unless it named something that
   * is gone — then what it fell back to.
   */
  preference: string
  catalog: ModelCatalog | undefined
  /** Providers the promoter has a key for, in display order. */
  keys: Provider[]
  error: unknown
}

/**
 * What to actually send, given a saved choice (see `lib/modelChoice`).
 */
export function useModelChoice(value: string): ModelChoice {
  const { data: catalog, error } = useSWR<ModelCatalog>("/api/models", fetcher)
  const { data: status } = useSWR<ApiKeyStatus>("/api/settings/api-key/status", fetcher)
  const resolved = resolveModel(value, catalog, status?.providers)
  return {
    ...resolved,
    preference: resolved.withdrawn || resolved.missingKey ? resolved.selected : value,
    catalog,
    keys: PROVIDERS.filter((p) => status?.providers?.includes(p)),
    error,
  }
}

interface ModelSelectProps {
  /** A saved choice — see `lib/modelChoice` for what the string can hold. */
  value: string
  onChange: (value: string) => void
  className: string
  labelClassName: string
}

/**
 * Picks what an action runs on: one of the promoter's own provider keys, or
 * a local model from those the admin has made available.
 */
export default function ModelSelect({
  value,
  onChange,
  className,
  labelClassName,
}: ModelSelectProps) {
  const { selected, provider, withdrawn, missingKey, needsKey, catalog, keys, error } =
    useModelChoice(value)
  const keysOnly = catalog?.local_enabled === false

  const unreachable =
    !keysOnly &&
    provider === undefined &&
    (error !== undefined || catalog?.local_available === false)

  const localOptions = (
    <>
      <option value={LOCAL_DEFAULT}>Domyślny{catalog ? ` (${catalog.default})` : ""}</option>
      {(catalog?.available ?? [])
        .filter((m) => m.name !== catalog?.default)
        .map((m) => (
          <option key={m.name} value={m.name}>
            {m.name}
            {m.parameter_size ? ` · ${m.parameter_size}` : ""}
          </option>
        ))}
    </>
  )

  const keyOptions = keys.map((p) => (
    <option key={p} value={byokValue(p)}>
      {PROVIDER_LABELS[p]}
      {catalog?.byok[p] ? ` · ${catalog.byok[p]}` : ""}
    </option>
  ))

  return (
    <label className="block">
      <span className={labelClassName}>Model</span>
      <select
        value={selected}
        onChange={(e) => onChange(e.target.value)}
        className={className}
        data-testid="model-select"
      >
        {keysOnly ? (
          keys.length === 0 ? (
            <option value="">Brak klucza API</option>
          ) : (
            <>
              {selected === "" && <option value="">Wybierz klucz API</option>}
              {keyOptions}
            </>
          )
        ) : keys.length === 0 ? (
          localOptions
        ) : (
          <>
            <optgroup label="Twoje klucze API">{keyOptions}</optgroup>
            <optgroup label="Modele lokalne">{localOptions}</optgroup>
          </>
        )}
      </select>
      {provider && (
        <span data-testid="model-byok" className="mt-1 block text-[11.5px] text-muted">
          Akcja pójdzie na Twoje konto u dostawcy.
        </span>
      )}
      {withdrawn && (
        <span data-testid="model-withdrawn" className="mt-1 block text-[11.5px] text-major-text">
          Model {withdrawn} z Twoich ustawień nie jest już dostępny — używam
          domyślnego.
        </span>
      )}
      {missingKey && !needsKey && (
        <span data-testid="model-key-missing" className="mt-1 block text-[11.5px] text-major-text">
          Klucz {PROVIDER_LABELS[missingKey]} z Twoich ustawień został usunięty —
          używam domyślnego modelu lokalnego.
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
      {unreachable && (
        <span className="mt-1 block text-[11.5px] text-muted">
          Nie udało się pobrać listy modeli — zostaje domyślny.
        </span>
      )}
    </label>
  )
}
