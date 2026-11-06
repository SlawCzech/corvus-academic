"use client"

import { useState } from "react"
import {
  acceptDraft,
  clearDraftAcceptance,
  deleteDraft,
  draftFileUrl,
} from "@/lib/api.client"
import type { ThesisDraft } from "@/lib/api.types"

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })
}

function formatSize(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} kB`
}

interface DraftListProps {
  studentId: string
  drafts: ThesisDraft[]
  /** Called with the whole list after any change — one change moves the others' dates. */
  onChange: (drafts: ThesisDraft[]) => void
}

/**
 * The thesis versions of one student, with what can be done to each.
 *
 * A purged version stays in the list: its number, date and length are the
 * trace that keeps the action history readable after the text is gone.
 */
export default function DraftList({ studentId, drafts, onChange }: DraftListProps) {
  const [busyId, setBusyId] = useState<string | null>(null)
  const [confirmingId, setConfirmingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function run(draftId: string, change: () => Promise<ThesisDraft[]>): Promise<void> {
    setBusyId(draftId)
    setError(null)
    try {
      onChange(await change())
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać zmiany")
    } finally {
      setBusyId(null)
      setConfirmingId(null)
    }
  }

  if (drafts.length === 0) {
    return (
      <div className="rounded-xl border border-line bg-surface p-2">
        <p className="p-4 text-[13.5px] text-muted">Brak przesłanych wersji.</p>
      </div>
    )
  }

  const linkButton =
    "text-[12.5px] font-medium text-accent hover:underline disabled:cursor-default disabled:text-muted disabled:no-underline"

  return (
    <div>
      <p className="mb-3 text-[12.5px] text-muted">
        Po zaakceptowaniu wersji finalnej pozostałe są usuwane po 14 dniach. Po
        zakończeniu opieki nad studentem wszystkie wersje są usuwane po 30 dniach.
        Zostaje ślad: numer, data, nazwa pliku i liczba znaków.
      </p>
      {error && (
        <p role="alert" className="mb-3 text-[13px] text-critical-text">
          {error}
        </p>
      )}
      <div className="rounded-xl border border-line bg-surface">
        {drafts.map((draft, i) => {
          const purged = draft.purged_at !== null
          const busy = busyId === draft.id
          return (
            <div
              key={draft.id}
              data-testid={`draft-${draft.version_number}`}
              className={`px-4 py-3 text-[13.5px] ${i > 0 ? "border-t border-line/60" : ""}`}
            >
              <div className="flex items-baseline justify-between gap-4">
                <span className={purged ? "text-muted" : "text-foreground"}>
                  <span className="font-semibold">v{draft.version_number}</span>{" "}
                  {draft.filename}
                  {draft.is_accepted && (
                    <span className="ml-2 rounded-md bg-success-bg px-1.5 py-0.5 text-[11.5px] font-semibold text-success-text">
                      wersja finalna
                    </span>
                  )}
                </span>
                <span className="shrink-0 text-muted">
                  {draft.char_count.toLocaleString("pl-PL")} znaków
                  {draft.file_size !== null && !purged ? ` · ${formatSize(draft.file_size)}` : ""}
                  {" · "}
                  {formatDate(draft.created_at)}
                </span>
              </div>

              <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1">
                {purged && draft.purged_at && (
                  <span className="text-[12.5px] text-muted">
                    Treść usunięta {formatDate(draft.purged_at)}
                  </span>
                )}
                {!purged && draft.purge_due_at && (
                  <span className="text-[12.5px] text-major-text">
                    Zostanie usunięta {formatDate(draft.purge_due_at)}
                  </span>
                )}

                {!purged && draft.has_file && (
                  <a href={draftFileUrl(studentId, draft.id)} className={linkButton}>
                    Pobierz plik
                  </a>
                )}
                {!purged &&
                  (draft.is_accepted ? (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void run(draft.id, () => clearDraftAcceptance(studentId, draft.id))}
                      className={linkButton}
                    >
                      Cofnij akceptację
                    </button>
                  ) : (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void run(draft.id, () => acceptDraft(studentId, draft.id))}
                      className={linkButton}
                    >
                      Zaakceptuj jako finalną
                    </button>
                  ))}
                {!purged &&
                  (confirmingId === draft.id ? (
                    <span className="text-[12.5px] text-critical-text">
                      Usunąć treść i plik tej wersji na stałe?{" "}
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void run(draft.id, () => deleteDraft(studentId, draft.id))}
                        className="font-semibold hover:underline"
                      >
                        Usuń
                      </button>{" "}
                      <button
                        type="button"
                        onClick={() => setConfirmingId(null)}
                        className="text-muted hover:underline"
                      >
                        Anuluj
                      </button>
                    </span>
                  ) : (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => setConfirmingId(draft.id)}
                      className="text-[12.5px] font-medium text-muted hover:text-critical-text"
                    >
                      Usuń wersję
                    </button>
                  ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
