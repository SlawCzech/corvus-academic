"use client"

import { useState } from "react"
import useSWR, { useSWRConfig } from "swr"
import ModelSelect, { useModelChoice } from "@/components/ai/ModelSelect"
import RubricView from "@/components/guidelines/RubricView"
import {
  draftGuidelineRubric,
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

const BUTTON =
  "h-9 rounded-lg border border-line px-4 text-[13px] font-medium text-foreground hover:bg-surface-alt transition-colors disabled:opacity-50"

function parseThreshold(value: string): number | null {
  const trimmed = value.trim()
  return trimmed === "" ? null : Number(trimmed)
}

interface Props {
  versionId: string
  onDone: () => void
}

/**
 * A draft version of a guideline set, from regulation to published rubric.
 *
 * The admin attaches the regulation and the model writes the rubric from it
 * — four sections and the thresholds (ADR 0024). The admin then reads it
 * against the original, corrects what needs it and publishes. Publishing
 * freezes the version and replaces the one in force.
 */
export default function GuidelineDraftEditor({ versionId, onDone }: Props) {
  const key = `/api/admin/guidelines/versions/${versionId}`
  const { mutate } = useSWRConfig()
  const { data: loaded } = useSWR<GuidelineVersion>(key, fetcher, {
    // While the model reads, ask again: the result lands on a read.
    refreshInterval: (latest) => (latest?.drafting ? 3000 : 0),
  })
  const [edited, setEdited] = useState<{
    rubric: string
    thresholds: Record<keyof Thresholds, string>
    effectiveFrom: string
  } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [preview, setPreview] = useState(true)
  const [model, setModel] = useState("")
  const { provider, needsKey } = useModelChoice(model)
  // A draft that has just come in replaces whatever the form held.
  const [wasDrafting, setWasDrafting] = useState(false)
  if (loaded?.drafting && !wasDrafting) setWasDrafting(true)
  if (loaded && !loaded.drafting && wasDrafting) {
    setWasDrafting(false)
    setEdited(null)
  }

  if (!loaded) return <p className="text-[13px] text-muted">Wczytywanie szkicu…</p>

  const drafting = Boolean(loaded.drafting)
  const locked = busy || drafting
  const form = edited ?? {
    rubric: loaded.rubric_md,
    thresholds: Object.fromEntries(
      THRESHOLD_FIELDS.map(({ key: k }) => [k, loaded.thresholds[k]?.toString() ?? ""]),
    ) as Record<keyof Thresholds, string>,
    effectiveFrom: loaded.effective_from ?? "",
  }

  function change(next: Partial<typeof form>): void {
    setEdited({ ...form, ...next })
    setSaved(false)
  }

  async function save(): Promise<boolean> {
    const thresholds = Object.fromEntries(
      THRESHOLD_FIELDS.map(({ key: k }) => [k, parseThreshold(form.thresholds[k])]),
    ) as unknown as Thresholds
    await mutate(
      key,
      await updateGuidelineDraft(versionId, {
        rubric_md: form.rubric,
        thresholds,
        effective_from: form.effectiveFrom || null,
      }),
      { revalidate: false },
    )
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

  async function draft(): Promise<void> {
    if (!provider) return
    await mutate(key, await draftGuidelineRubric(versionId, provider), { revalidate: false })
  }

  return (
    <div className="rounded-xl border border-line bg-surface p-5">
      <h3 className="mb-1 text-[15px] font-semibold text-foreground">
        {loaded.set_name} · szkic wersji {loaded.version_no}
      </h3>
      <p className="mb-5 text-[12.5px] text-muted">{loaded.university.name}</p>

      <section className="mb-5 rounded-lg bg-surface-alt p-4">
        <h4 className="mb-2 text-[13.5px] font-semibold text-foreground">
          1. Regulamin uczelni
        </h4>
        {loaded.source ? (
          <p data-testid="draft-source" className="mb-2 text-[13px] text-foreground">
            {loaded.source.filename}
          </p>
        ) : (
          <p className="mb-2 text-[12.5px] text-muted">
            Wgraj zarządzenie albo regulamin, z którego Corvus ma zbudować rubrykę.
          </p>
        )}
        <input
          type="file"
          accept=".pdf,.docx"
          aria-label="Oryginał zarządzenia"
          disabled={locked}
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) {
              void run(async () =>
                mutate(key, await uploadGuidelineSource(versionId, file), {
                  revalidate: false,
                }),
              )
            }
          }}
          className="text-[13px] text-muted"
        />

        <h4 className="mb-2 mt-4 text-[13.5px] font-semibold text-foreground">
          2. Rubryka z regulaminu
        </h4>
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-64">
            <ModelSelect
              value={model}
              onChange={setModel}
              className={INPUT}
              labelClassName="mb-1 block text-[11.5px] text-muted"
            />
          </div>
          <button
            type="button"
            data-testid="draft-rubric"
            disabled={locked || !loaded.source || needsKey || !provider}
            onClick={() => void run(draft)}
            className="h-9 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
          >
            {form.rubric.trim() ? "Zbuduj rubrykę od nowa" : "Zbuduj rubrykę"}
          </button>
        </div>
        {drafting ? (
          <p data-testid="drafting" className="mt-2.5 text-[12.5px] text-accent-hover">
            Corvus czyta regulamin i pisze rubrykę. To trwa zwykle minutę lub dwie.
          </p>
        ) : (
          <p className="mt-2.5 text-[12px] text-muted">
            Model czyta cały regulamin i pisze cztery sekcje rubryki oraz progi. Idzie na
            Twój klucz{form.rubric.trim() ? " i zastąpi to, co jest niżej" : ""}.
          </p>
        )}
        {loaded.drafting_error && !drafting && (
          <p role="alert" className="mt-2 text-[12.5px] text-critical-text">
            Szkic się nie udał: {loaded.drafting_error}
          </p>
        )}
      </section>

      <section className="mb-5">
        <div className="mb-2 flex items-baseline justify-between gap-3">
          <h4 className="text-[13.5px] font-semibold text-foreground">
            3. Sprawdź z oryginałem i popraw
          </h4>
          <div className="flex gap-1 text-[12.5px]" role="tablist">
            {[
              { on: true, label: "Podgląd" },
              { on: false, label: "Markdown" },
            ].map(({ on, label }) => (
              <button
                key={label}
                type="button"
                role="tab"
                aria-selected={preview === on}
                onClick={() => setPreview(on)}
                className={`rounded-md px-2.5 py-1 ${
                  preview === on ? "bg-accent-soft text-accent-hover" : "text-muted"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        {preview ? (
          form.rubric.trim() ? (
            <RubricView rubric={form.rubric} />
          ) : (
            <p className="rounded-lg border border-dashed border-line p-5 text-[13px] text-muted">
              Rubryki jeszcze nie ma. Zbuduj ją z regulaminu albo napisz w zakładce
              Markdown.
            </p>
          )
        ) : (
          <>
            <p className="mb-1.5 text-[12px] text-muted">
              Dokładnie cztery sekcje, każda raz:{" "}
              {RUBRIC_SECTIONS.map((s) => `„## ${s.heading}”`).join(", ")}. Bez liczb —
              te idą w progi niżej. Wersja bez tych sekcji się nie opublikuje.
            </p>
            <textarea
              id="rubric"
              aria-label="Rubryka dla modelu (markdown)"
              value={form.rubric}
              disabled={locked}
              onChange={(e) => change({ rubric: e.target.value })}
              rows={20}
              className={`${INPUT} font-mono text-[12.5px]`}
            />
          </>
        )}
      </section>

      <div className="mb-5 grid grid-cols-2 gap-3">
        {THRESHOLD_FIELDS.map(({ key: k, label }) => (
          <label key={k} className="text-[12.5px] font-medium text-muted-strong">
            {label}
            <input
              type="number"
              min={0}
              value={form.thresholds[k]}
              disabled={locked}
              onChange={(e) => change({ thresholds: { ...form.thresholds, [k]: e.target.value } })}
              className={`${INPUT} mt-1`}
            />
          </label>
        ))}
        <label className="text-[12.5px] font-medium text-muted-strong">
          Obowiązuje od
          <input
            type="date"
            value={form.effectiveFrom}
            disabled={locked}
            onChange={(e) => change({ effectiveFrom: e.target.value })}
            className={`${INPUT} mt-1`}
          />
        </label>
      </div>

      {error && (
        <p role="alert" className="mb-3 text-[13px] text-critical-text">
          {error}
        </p>
      )}

      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={locked}
          onClick={() => void run(async () => setSaved(await save()))}
          className={BUTTON}
        >
          Zapisz szkic
        </button>
        <button
          type="button"
          disabled={locked || !form.rubric.trim()}
          onClick={() =>
            void run(async () => {
              await save()
              await publishGuidelineVersion(versionId)
              onDone()
            })
          }
          className="h-9 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
        >
          Opublikuj
        </button>
        <button type="button" onClick={onDone} className="text-[13px] text-muted hover:underline">
          Zamknij
        </button>
        {saved && <span className="text-[12.5px] text-success-text">Zapisano</span>}
      </div>
      <p className="mt-3 text-[12px] text-muted">
        Promotorzy zobaczą rubrykę dopiero po publikacji. Opublikowanej wersji nie można
        już zmienić: poprawka to nowa wersja, a poprzednia zostanie oznaczona jako
        zastąpiona.
      </p>
    </div>
  )
}
