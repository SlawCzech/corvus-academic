"use client"

import { useState } from "react"
import useSWR, { useSWRConfig } from "swr"
import { IconAlertTriangle } from "@tabler/icons-react"
import { fetcher, setDefaultModel, setModelEnabled } from "@/lib/api.client"
import type { AdminModel, AdminModelCatalog } from "@/lib/api.types"

const KEY = "/api/admin/models"

/**
 * The admin's allowlist of local models.
 *
 * Lists what the server has installed; each model is either offered to
 * promoters or not, and exactly one is the default. Installing a new model
 * stays a server task (`ollama pull`) — it shows up here once it is there.
 */
export default function ModelAdmin() {
  const { data, error, mutate } = useSWR<AdminModelCatalog>(KEY, fetcher)
  const { mutate: mutateGlobal } = useSWRConfig()
  const [busy, setBusy] = useState<string | null>(null)
  const [failure, setFailure] = useState<string | null>(null)

  async function apply(name: string, change: () => Promise<AdminModelCatalog>): Promise<void> {
    setBusy(name)
    setFailure(null)
    try {
      await mutate(await change(), { revalidate: false })
      // The promoters' picker reads a different key; keep it in step.
      void mutateGlobal("/api/models")
    } catch (err) {
      setFailure(err instanceof Error ? err.message : "Nie udało się zapisać zmiany")
    } finally {
      setBusy(null)
    }
  }

  if (error) {
    return (
      <p className="text-[13px] text-critical-text">
        Nie udało się pobrać listy modeli — sprawdź, czy działa serwis agenta.
      </p>
    )
  }
  if (!data) return <p className="text-[13px] text-muted">Wczytywanie…</p>
  if (!data.local_enabled) {
    return (
      <p className="rounded-lg border border-line bg-surface px-4 py-3 text-[13px] text-muted">
        Modele lokalne są na tym serwerze wyłączone (<code>LOCAL_MODELS_ENABLED=false</code>).
        Promotorzy uruchamiają akcje na własnych kluczach API do Claude albo OpenAI.
      </p>
    )
  }

  return (
    <div>
      <p className="mb-8 text-[13.5px] text-muted">
        Promotorzy wybierają tylko spośród udostępnionych modeli. Domyślny działa,
        gdy promotor niczego nie wybierze, i nie da się go wyłączyć, dopóki nie
        wskażesz innego. Nowy model instaluje się na serwerze (
        <code className="font-mono text-[12.5px]">ollama pull</code>) — pojawi się
        tu wtedy sam, jako nieudostępniony.
      </p>
      {!data.local_available && (
        <p className="mb-4 flex items-center gap-2 rounded-lg border border-major-border bg-major-bg px-4 py-3 text-[13px] text-major-text">
          <IconAlertTriangle size={16} stroke={1.75} />
          Agent nie może połączyć się z Ollamą — widać tylko zapisane ustawienia.
        </p>
      )}

      <div className="overflow-hidden rounded-xl border border-line bg-surface">
        <table className="w-full text-left text-[13.5px]">
          <thead>
            <tr className="border-b border-line text-[11.5px] uppercase tracking-wide text-muted">
              <th className="py-2.5 pl-6 font-semibold">Model</th>
              <th className="py-2.5 font-semibold">Rozmiar</th>
              <th className="py-2.5 text-center font-semibold">Udostępniony</th>
              <th className="py-2.5 pr-6 text-center font-semibold">Domyślny</th>
            </tr>
          </thead>
          <tbody>
            {data.models.map((m) => (
              <ModelRow
                key={m.name}
                model={m}
                busy={busy === m.name}
                onEnabled={(enabled) => void apply(m.name, () => setModelEnabled(m.name, enabled))}
                onDefault={() => void apply(m.name, () => setDefaultModel(m.name))}
              />
            ))}
          </tbody>
        </table>
      </div>

      {failure && (
        <p data-testid="model-admin-error" className="mt-3 text-[13px] text-critical-text">
          {failure}
        </p>
      )}
    </div>
  )
}

function ModelRow({
  model,
  busy,
  onEnabled,
  onDefault,
}: {
  model: AdminModel
  busy: boolean
  onEnabled: (enabled: boolean) => void
  onDefault: () => void
}) {
  return (
    <tr className="border-b border-line/60 last:border-none">
      <td className="py-3.5 pl-6">
        <span className="font-mono text-[13px] text-foreground">{model.name}</span>
        {!model.installed && (
          <span className="mt-0.5 block text-[12px] text-major-text">
            Nie ma go już na serwerze
            {model.is_default ? " — wskaż inny model domyślny" : ""}
          </span>
        )}
      </td>
      <td className="py-3.5 text-muted">{model.parameter_size ?? "—"}</td>
      <td className="py-3.5 text-center">
        <input
          type="checkbox"
          aria-label={`Udostępnij ${model.name}`}
          checked={model.enabled}
          // The default cannot be withdrawn — promoters would be left with
          // nothing to fall back on. Pick another default first.
          disabled={busy || model.is_default || (!model.installed && !model.enabled)}
          title={model.is_default ? "Model domyślny jest zawsze udostępniony" : undefined}
          onChange={(e) => onEnabled(e.target.checked)}
          className="h-4 w-4 accent-[var(--accent)] disabled:opacity-40"
        />
      </td>
      <td className="py-3.5 pr-6 text-center">
        <input
          type="radio"
          name="default-model"
          aria-label={`Ustaw ${model.name} jako domyślny`}
          checked={model.is_default}
          disabled={busy || !model.installed}
          onChange={onDefault}
          className="h-4 w-4 accent-[var(--accent)] disabled:opacity-40"
        />
      </td>
    </tr>
  )
}
