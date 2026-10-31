"use client"

import { useState } from "react"
import ActionProgress from "@/components/students/ActionProgress"
import { useModelChoice } from "@/components/ai/ModelSelect"
import { isUnfinished } from "@/hooks/useAction"
import {
  deleteFragment,
  fragmentFileUrl,
  saveFragmentFeedback,
  triggerAction,
} from "@/lib/api.client"
import type { FragmentEntry, FragmentVerdict } from "@/lib/api.types"
import { useAiDefaults } from "@/lib/aiDefaults"
import {
  fragmentFeedbackDraft,
  fragmentReview,
  PART_STATE_STYLES,
  VERDICT_LABELS,
} from "@/lib/fragmentFeedback"

const VERDICTS: FragmentVerdict[] = ["on_track", "needs_changes", "needs_additions"]

const linkButton = "text-[12.5px] font-medium text-accent hover:underline"

/**
 * One fragment on the timeline. One waiting for an answer is open, with the
 * draft in the box; one answered is a line that opens on a click.
 */
export default function FragmentCard({
  studentId,
  entry,
  onChange,
}: {
  studentId: string
  entry: FragmentEntry
  onChange: () => void
}) {
  const [open, setOpen] = useState(entry.verdict === null)
  const review = entry.review

  return (
    <div data-testid="fragment-card" className="rounded-xl border border-line bg-surface">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left"
      >
        <span className="min-w-0 truncate text-[13.5px] font-medium text-foreground">
          {entry.part_name}, runda {entry.round_number}
        </span>
        {entry.verdict && (
          <span
            className={`shrink-0 rounded-md px-2 py-0.5 text-[12.5px] font-medium ${PART_STATE_STYLES[entry.verdict]}`}
          >
            {VERDICT_LABELS[entry.verdict]}
          </span>
        )}
      </button>
      {!open && (entry.summary || entry.preview) && (
        <p className="line-clamp-2 px-4 pb-3 text-[13px] text-muted">
          {entry.summary ?? entry.preview}
        </p>
      )}
      {open && (
        <div className="border-t border-line/60 px-4 py-3">
          <div className="mb-3 flex flex-wrap items-center gap-x-3 text-[12.5px] text-muted">
            {entry.has_file && (
              <a href={fragmentFileUrl(studentId, entry.id)} className={linkButton}>
                {entry.filename}
              </a>
            )}
            {entry.format === "text" && <span>Tekst wklejony</span>}
            {entry.purged_at && <span>Tekst usunięty zgodnie z retencją</span>}
            <span>{entry.char_count.toLocaleString("pl-PL")} znaków</span>
          </div>
          {entry.question && (
            <p className="mb-3 text-[13px] text-muted-strong">
              Pytanie: {entry.question}
            </p>
          )}
          <Summary entry={entry} studentId={studentId} onChange={onChange} />
          <FeedbackForm
            // A finished run replaces what the box was showing.
            key={`${review?.id ?? "none"}:${review?.status ?? ""}`}
            studentId={studentId}
            entry={entry}
            onChange={onChange}
          />
          <DeleteFragment studentId={studentId} entry={entry} onChange={onChange} />
        </div>
      )}
    </div>
  )
}

function Summary({
  studentId,
  entry,
  onChange,
}: {
  studentId: string
  entry: FragmentEntry
  onChange: () => void
}) {
  const defaults = useAiDefaults()
  const { provider, model, needsKey } = useModelChoice(defaults.model)
  const [error, setError] = useState<string | null>(null)
  const review = entry.review

  async function run(): Promise<void> {
    setError(null)
    try {
      await triggerAction(studentId, "review_fragment", undefined, {
        provider,
        model,
        language: defaults.language,
        fragmentId: entry.id,
      })
      onChange()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się uruchomić akcji")
    }
  }

  if (review && isUnfinished(review)) {
    return (
      <div className="mb-3" data-testid="fragment-running">
        <p className="mb-1 text-[13px] text-muted">AI czyta fragment…</p>
        {review.progress && <ActionProgress progress={review.progress} />}
      </div>
    )
  }
  return (
    <div className="mb-3">
      {entry.summary ? (
        <div data-testid="fragment-summary">
          <h4 className="mb-1 text-[12.5px] font-medium text-muted-strong">
            Co zostało oddane
          </h4>
          <p className="whitespace-pre-wrap text-[13.5px] text-foreground">
            {entry.summary}
          </p>
        </div>
      ) : (
        <>
          {review?.status === "failed" && (
            <p className="mb-1 text-[13px] text-critical-text">
              {review.error ?? "Nie udało się przygotować podsumowania"}
            </p>
          )}
          {entry.preview && (
            <p className="mb-1 text-[13px] text-muted">{entry.preview}</p>
          )}
        </>
      )}
      {!entry.summary && !entry.purged_at && (
        <button
          type="button"
          disabled={needsKey}
          onClick={() => void run()}
          className={`${linkButton} disabled:text-muted disabled:no-underline`}
        >
          {needsKey ? "Dodaj klucz API, by uruchomić AI" : "Uruchom AI"}
        </button>
      )}
      {error && (
        <p role="alert" className="mt-1 text-[13px] text-critical-text">
          {error}
        </p>
      )}
    </div>
  )
}

function FeedbackForm({
  studentId,
  entry,
  onChange,
}: {
  studentId: string
  entry: FragmentEntry
  onChange: () => void
}) {
  const review = entry.review?.status === "completed" ? entry.review : null
  const draft = fragmentReview(review?.output ?? null)
  const [text, setText] = useState(
    entry.feedback ?? (draft ? fragmentFeedbackDraft(draft) : ""),
  )
  const [verdict, setVerdict] = useState<FragmentVerdict | null>(
    entry.verdict ?? draft?.direction ?? null,
  )
  const [nextDue, setNextDue] = useState("")
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function save(copy: boolean): Promise<void> {
    if (!verdict) {
      setError("Wybierz ocenę, zanim zapiszesz")
      return
    }
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await saveFragmentFeedback(studentId, entry.id, {
        verdict,
        feedback: text.trim() || null,
        sourceActionId: review && text.trim() ? review.id : null,
        nextDueOn: nextDue || null,
      })
      if (copy) await copyToClipboard(text)
      onChange()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać feedbacku")
    } finally {
      setBusy(false)
    }
  }

  async function copyToClipboard(value: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(value)
      setNotice("Zapisano i skopiowano")
    } catch {
      setNotice("Zapisano. Schowek jest niedostępny, skopiuj tekst ręcznie.")
    }
  }

  return (
    <div>
      {draft && !entry.verdict && (
        <p className="mb-1 text-[12.5px] text-muted">
          Sugestia AI: {VERDICT_LABELS[draft.direction]}. Ocena jest Twoja.
        </p>
      )}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={7}
        aria-label="Feedback dla studenta"
        placeholder="Co przekażesz studentowi?"
        className="mb-3 w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13.5px] text-foreground focus:border-accent focus:outline-none"
      />
      <div className="mb-3 flex flex-wrap items-center gap-2" role="group" aria-label="Ocena">
        {VERDICTS.map((option) => (
          <button
            key={option}
            type="button"
            aria-pressed={verdict === option}
            onClick={() => setVerdict(option)}
            className={`h-8 rounded-lg border px-3 text-[13px] font-medium transition-colors ${
              verdict === option
                ? "border-accent bg-accent-soft text-accent-hover"
                : "border-line text-foreground hover:bg-surface-alt"
            }`}
          >
            {VERDICT_LABELS[option]}
          </button>
        ))}
        <label className="ml-auto flex items-center gap-2 text-[12.5px] text-muted">
          Następny termin
          <input
            type="date"
            value={nextDue}
            onChange={(e) => setNextDue(e.target.value)}
            className="bg-transparent text-[12.5px] text-foreground focus:outline-none"
          />
        </label>
      </div>
      {error && (
        <p role="alert" className="mb-2 text-[13px] text-critical-text">
          {error}
        </p>
      )}
      {notice && <p className="mb-2 text-[13px] text-success-text">{notice}</p>}
      <div className="flex gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => void save(true)}
          className="h-9 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
        >
          Zapisz i kopiuj do maila
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void save(false)}
          className="h-9 rounded-lg border border-line px-4 text-[13px] font-medium text-foreground hover:bg-surface-alt disabled:opacity-50"
        >
          Zapisz
        </button>
      </div>
    </div>
  )
}

function DeleteFragment({
  studentId,
  entry,
  onChange,
}: {
  studentId: string
  entry: FragmentEntry
  onChange: () => void
}) {
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function remove(): Promise<void> {
    setError(null)
    try {
      await deleteFragment(studentId, entry.id)
      onChange()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się usunąć fragmentu")
    }
  }

  return (
    <div className="mt-3 border-t border-line/60 pt-2 text-[12.5px]">
      {confirming ? (
        <span className="text-muted">
          Usunąć fragment z plikiem i wynikami AI?{" "}
          <button
            type="button"
            onClick={() => void remove()}
            className="font-medium text-critical-text hover:underline"
          >
            Tak, usuń
          </button>{" "}
          <button
            type="button"
            onClick={() => setConfirming(false)}
            className="font-medium text-muted-strong hover:underline"
          >
            Nie
          </button>
        </span>
      ) : (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          className="text-muted hover:text-critical-text"
        >
          Usuń fragment
        </button>
      )}
      {error && (
        <p role="alert" className="mt-1 text-critical-text">
          {error}
        </p>
      )}
    </div>
  )
}
