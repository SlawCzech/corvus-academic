"use client"

import { useState } from "react"
import useSWR from "swr"
import {
  fetcher,
  publishGuidelineVersion,
  updateGuidelineDraft,
  uploadGuidelineSource,
} from "@/lib/api.client"
import type { GuidelineVersion, Thresholds } from "@/lib/api.types"
import { THRESHOLD_FIELDS } from "@/components/guidelines/format"
import { RUBRIC_SECTIONS } from "@/components/guidelines/rubric"

const INPUT =
  "w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[13.5px] text-foreground focus:border-accent focus:outline-none"

function parseThreshold(value: string): number | null {
  const trimmed = value.trim()
  return trimmed === "" ? null : Number(trimmed)
}

interface Props {
  versionId: string
  onDone: () => void
}

/**
 * Edit a draft version of a guideline set: the rubric the model will read,
 * the numbers code can check, the date it applies from, and the original
 * regulation. Publishing freezes it and replaces the version in force.
 */
export default function GuidelineDraftEditor({ versionId, onDone }: Props) {
  const { data: loaded } = useSWR<GuidelineVersion>(
    `/api/guidelines/versions/${versionId}`,
    fetcher,
  )
  const [edited, setEdited] = useState<{
    rubric: string
    thresholds: Record<keyof Thresholds, string>
    effectiveFrom: string
  } | null>(null)
  const [source, setSource] = useState<GuidelineVersion["source"] | undefined>(undefined)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  if (!loaded) return <p className="text-[13px] text-muted">Wczytywanie szkicu…</p>

  const form = edited ?? {
    rubric: loaded.rubric_md,
    thresholds: Object.fromEntries(
      THRESHOLD_FIELDS.map(({ key }) => [key, loaded.thresholds[key]?.toString() ?? ""]),
    ) as Record<keyof Thresholds, string>,
    effectiveFrom: loaded.effective_from ?? "",
  }
  const currentSource = source === undefined ? loaded.source : source

  function change(next: Partial<typeof form>): void {
    setEdited({ ...form, ...next })
    setSaved(false)
  }

  async function save(): Promise<boolean> {
    const thresholds = Object.fromEntries(
      THRESHOLD_FIELDS.map(({ key }) => [key, parseThreshold(form.thresholds[key])]),
    ) as unknown as Thresholds
    await updateGuidelineDraft(versionId, {
      rubric_md: form.rubric,
      thresholds,
      effective_from: form.effectiveFrom || null,
    })
    return true
  }

  async function run(step: () => Promise<unknown>): Promise<void> {
    setBusy(true)
    setError(null)
    try {
      await step()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-xl border border-line bg-surface p-5">
      <h3 className="mb-4 text-[15px] font-semibold text-foreground">
        Szkic wersji {loaded.version_no}
      </h3>

      <label className="mb-1 block text-[12.5px] font-medium text-muted-strong" htmlFor="rubric">
        Rubryka dla modelu (markdown)
      </label>
      <p className="mb-1.5 text-[12px] text-muted">
        Dokładnie cztery sekcje, każda raz:{" "}
        {RUBRIC_SECTIONS.map((s) => `„## ${s.heading}”`).join(", ")}. Bez liczb — te
        idą w progi niżej. Wersja bez tych sekcji się nie opublikuje.
      </p>
      <textarea
        id="rubric"
        value={form.rubric}
        onChange={(e) => change({ rubric: e.target.value })}
        rows={16}
        className={`${INPUT} mb-4 font-mono text-[12.5px]`}
      />

      <div className="mb-4 grid grid-cols-2 gap-3">
        {THRESHOLD_FIELDS.map(({ key, label }) => (
          <label key={key} className="text-[12.5px] font-medium text-muted-strong">
            {label}
            <input
              type="number"
              min={0}
              value={form.thresholds[key]}
              onChange={(e) =>
                change({ thresholds: { ...form.thresholds, [key]: e.target.value } })
              }
              className={`${INPUT} mt-1`}
            />
          </label>
        ))}
        <label className="text-[12.5px] font-medium text-muted-strong">
          Obowiązuje od
          <input
            type="date"
            value={form.effectiveFrom}
            onChange={(e) => change({ effectiveFrom: e.target.value })}
            className={`${INPUT} mt-1`}
          />
        </label>
      </div>

      <div className="mb-5">
        <span className="mb-1 block text-[12.5px] font-medium text-muted-strong">
          Oryginał zarządzenia (PDF/DOCX)
        </span>
        {currentSource && (
          <p className="mb-1.5 text-[13px] text-foreground">{currentSource.filename}</p>
        )}
        <input
          type="file"
          accept=".pdf,.docx"
          aria-label="Oryginał zarządzenia"
          disabled={busy}
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) {
              void run(async () => setSource((await uploadGuidelineSource(versionId, file)).source))
            }
          }}
          className="text-[13px] text-muted"
        />
      </div>

      {error && (
        <p role="alert" className="mb-3 text-[13px] text-critical-text">
          {error}
        </p>
      )}

      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={busy}
          onClick={() => void run(async () => setSaved(await save()))}
          className="h-9 rounded-lg border border-line px-4 text-[13px] font-medium text-foreground hover:bg-surface-alt transition-colors"
        >
          Zapisz szkic
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            void run(async () => {
              await save()
              await publishGuidelineVersion(versionId)
              onDone()
            })
          }
          className="h-9 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors"
        >
          Opublikuj
        </button>
        <button
          type="button"
          onClick={onDone}
          className="text-[13px] text-muted hover:underline"
        >
          Zamknij
        </button>
        {saved && <span className="text-[12.5px] text-success-text">Zapisano</span>}
      </div>
      <p className="mt-3 text-[12px] text-muted">
        Opublikowanej wersji nie można już zmienić. Poprawka to nowa wersja; poprzednia
        zostanie oznaczona jako zastąpiona.
      </p>
    </div>
  )
}
