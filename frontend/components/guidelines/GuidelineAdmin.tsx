"use client"

import Link from "next/link"
import { useState } from "react"
import useSWR from "swr"
import ModelSelect, { useModelChoice } from "@/components/ai/ModelSelect"
import GuidelineDraftEditor from "@/components/guidelines/GuidelineDraftEditor"
import {
  correctGuidelineSet,
  createGuidelineDraft,
  createGuidelineSet,
  deleteGuidelineSet,
  createUniversity,
  draftGuidelineRubric,
  fetcher,
  uploadGuidelineSource,
} from "@/lib/api.client"
import type { GuidelineSet, GuidelineSetDetail, University } from "@/lib/api.types"
import { THESIS_TYPE_LABELS } from "@/components/guidelines/format"

const INPUT =
  "rounded-lg border border-line bg-surface px-3 py-1.5 text-[13.5px] text-foreground focus:border-accent focus:outline-none"
const BUTTON =
  "h-9 rounded-lg border border-line px-4 text-[13px] font-medium text-foreground hover:bg-surface-alt transition-colors"

function groupByUniversity(sets: GuidelineSet[]): [string, GuidelineSet[]][] {
  const groups = new Map<string, GuidelineSet[]>()
  for (const set of sets) {
    groups.set(set.university.name, [...(groups.get(set.university.name) ?? []), set])
  }
  return [...groups.entries()]
}

/**
 * The catalog as an admin manages it. New guidelines start from the
 * university's regulation: the admin names the university and the kind of
 * thesis and uploads the file, and the model drafts the rubric (ADR 0025).
 */
export default function GuidelineAdmin() {
  const { data: sets, mutate: mutateSets } = useSWR<GuidelineSet[]>(
    "/api/guidelines/sets",
    fetcher,
  )
  const { data: universities, mutate: mutateUniversities } = useSWR<University[]>(
    "/api/guidelines/universities",
    fetcher,
  )
  const [editing, setEditing] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [universityName, setUniversityName] = useState("")
  const [universityShort, setUniversityShort] = useState("")
  const [setUniversity, setSetUniversity] = useState("")
  const [setThesisType, setSetThesisType] = useState("bachelor")
  const [setName, setSetName] = useState("")
  const [regulation, setRegulation] = useState<File | null>(null)
  const [fileKey, setFileKey] = useState(0)
  const [model, setModel] = useState("")
  const { provider, needsKey } = useModelChoice(model)
  const [busy, setBusy] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  /** A set, its first draft, the regulation on it, and the model reading it. */
  async function startFromRegulation(): Promise<void> {
    if (!regulation) return
    const created = await createGuidelineSet(setUniversity, setThesisType, setName)
    const draft = await createGuidelineDraft(created.id)
    await uploadGuidelineSource(draft.id, regulation)
    if (provider) await draftGuidelineRubric(draft.id, provider)
    setSetName("")
    setRegulation(null)
    setFileKey((k) => k + 1)
    await mutateSets()
    setEditing(draft.id)
  }

  async function run(step: () => Promise<unknown>): Promise<void> {
    setError(null)
    setBusy(true)
    try {
      await step()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać")
    } finally {
      setBusy(false)
    }
  }

  /** Open the set's draft, creating one from the version in force if there is none. */
  async function openDraft(set: GuidelineSet): Promise<void> {
    if (set.has_draft) {
      const detail = await fetcher<GuidelineSetDetail>(`/api/guidelines/sets/${set.id}`)
      const draft = detail.versions.find((v) => v.status === "draft")
      if (draft) setEditing(draft.id)
      return
    }
    // A published set is corrected with its regulation copied; one that never
    // got that far starts from a blank draft.
    const draft = set.current
      ? await correctGuidelineSet(set.id)
      : await createGuidelineDraft(set.id)
    await mutateSets()
    setEditing(draft.id)
  }

  async function remove(set: GuidelineSet): Promise<void> {
    if (confirmDelete !== set.id) {
      setConfirmDelete(set.id)
      return
    }
    await deleteGuidelineSet(set.id)
    setConfirmDelete(null)
    if (editing) setEditing(null)
    await mutateSets()
  }

  return (
    <div>
      {error && (
        <p role="alert" className="mb-4 text-[13px] text-critical-text">
          {error}
        </p>
      )}

      {editing && (
        <div className="mb-8">
          <GuidelineDraftEditor
            versionId={editing}
            onDone={() => {
              setEditing(null)
              void mutateSets()
            }}
          />
        </div>
      )}

      <form
        data-testid="new-guidelines"
        className="mb-8 rounded-xl border border-line bg-surface p-5"
        onSubmit={(e) => {
          e.preventDefault()
          void run(startFromRegulation)
        }}
      >
        <h2 className="mb-1 text-[15px] font-semibold text-foreground">
          Nowe wytyczne z regulaminu
        </h2>
        <p className="mb-4 text-[12.5px] text-muted">
          Wskaż uczelnię i typ pracy, wgraj zarządzenie. Corvus przeczyta je i napisze
          rubrykę z progami; sprawdzisz ją z oryginałem i opublikujesz.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <select
            required
            aria-label="Uczelnia"
            value={setUniversity}
            onChange={(e) => setSetUniversity(e.target.value)}
            className={`${INPUT} w-full`}
          >
            <option value="">Wybierz uczelnię…</option>
            {(universities ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </select>
          <select
            aria-label="Typ pracy"
            value={setThesisType}
            onChange={(e) => setSetThesisType(e.target.value)}
            className={`${INPUT} w-full`}
          >
            {Object.entries(THESIS_TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <input
            required
            placeholder="Prace licencjackie (zarządzenie 117/22, zał. 1)"
            aria-label="Nazwa zestawu"
            value={setName}
            onChange={(e) => setSetName(e.target.value)}
            className={`${INPUT} col-span-2 w-full`}
          />
          <label className="col-span-2 block text-[12.5px] text-muted-strong">
            Regulamin (PDF/DOCX)
            <input
              key={fileKey}
              type="file"
              accept=".pdf,.docx"
              aria-label="Regulamin"
              onChange={(e) => setRegulation(e.target.files?.[0] ?? null)}
              className="mt-1 block text-[13px] text-muted"
            />
          </label>
          <div className="col-span-2 w-64">
            <ModelSelect
              value={model}
              onChange={setModel}
              className={`${INPUT} w-full`}
              labelClassName="mb-1 block text-[11.5px] text-muted"
            />
          </div>
        </div>
        <button
          type="submit"
          data-testid="start-from-regulation"
          disabled={busy || !regulation || needsKey || !provider}
          className="mt-4 h-9 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
        >
          {busy ? "Wysyłanie…" : "Zbuduj rubrykę"}
        </button>
      </form>

      {(sets ?? []).length === 0 && (
        <p className="mb-8 text-[13.5px] text-muted">
          Brak zestawów. Dodaj pierwsze wytyczne z regulaminu powyżej.
        </p>
      )}
      {groupByUniversity(sets ?? []).map(([university, universitySets]) => (
        <section key={university} className="mb-6">
          <h2 className="mb-2 text-[14px] font-semibold text-foreground">{university}</h2>
          <div className="rounded-xl border border-line bg-surface">
            {universitySets.map((set, i) => (
              <div
                key={set.id}
                data-testid={`set-${set.id}`}
                className={`flex items-center justify-between gap-4 px-5 py-3.5 text-[13.5px] ${
                  i > 0 ? "border-t border-line/60" : ""
                }`}
              >
                <span>
                  <span className="block font-medium text-foreground">{set.name}</span>
                  <span className="text-[12.5px] text-muted">
                    {THESIS_TYPE_LABELS[set.thesis_type] ?? set.thesis_type} ·{" "}
                    {set.current ? (
                      <Link
                        href={`/guidelines/${set.current.id}`}
                        className="text-accent hover:underline"
                      >
                        wersja {set.current.version_no} obowiązuje
                      </Link>
                    ) : (
                      "nic jeszcze nie opublikowano"
                    )}
                    {set.has_draft && " · jest szkic"}
                  </span>
                </span>
                <span className="flex shrink-0 items-center gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    className={BUTTON}
                    onClick={() => void run(() => openDraft(set))}
                  >
                    {set.has_draft ? "Edytuj szkic" : set.current ? "Popraw" : "Nowy szkic"}
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    data-testid={`delete-set-${set.id}`}
                    className="h-9 rounded-lg px-3 text-[13px] font-medium text-critical-text hover:bg-surface-alt transition-colors"
                    onClick={() => void run(() => remove(set))}
                  >
                    {confirmDelete === set.id ? "Na pewno usunąć?" : "Usuń zestaw"}
                  </button>
                </span>
              </div>
            ))}
          </div>
        </section>
      ))}
      {confirmDelete && (
        <p className="-mt-3 mb-6 text-[12.5px] text-major-text">
          Usunięcie zabiera wszystkie wersje i oryginał. Studenci z tym zestawem będą
          musieli dostać inny, zanim pójdzie dla nich recenzja.
        </p>
      )}

      <div className="max-w-md">
        <form
          className="rounded-xl border border-line bg-surface p-5"
          onSubmit={(e) => {
            e.preventDefault()
            void run(async () => {
              await createUniversity(universityName, universityShort)
              setUniversityName("")
              setUniversityShort("")
              await mutateUniversities()
            })
          }}
        >
          <h2 className="mb-3 text-[14px] font-semibold text-foreground">
            Uczelni nie ma na liście? Dodaj ją
          </h2>
          <input
            required
            placeholder="Uniwersytet Ekonomiczny w Katowicach"
            aria-label="Nazwa uczelni"
            value={universityName}
            onChange={(e) => setUniversityName(e.target.value)}
            className={`${INPUT} mb-2 w-full`}
          />
          <input
            required
            placeholder="UE Katowice"
            aria-label="Skrót"
            value={universityShort}
            onChange={(e) => setUniversityShort(e.target.value)}
            className={`${INPUT} mb-3 w-full`}
          />
          <button type="submit" className={BUTTON}>
            Dodaj uczelnię
          </button>
        </form>
      </div>
    </div>
  )
}
