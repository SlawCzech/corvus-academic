"use client"

import { useState } from "react"
import { IconArrowDown, IconArrowUp, IconPlus, IconTrash } from "@tabler/icons-react"
import { addPart, deletePart, updatePart } from "@/lib/api.client"
import type { PartEntry } from "@/lib/api.types"
import { PART_STATE_LABELS, PART_STATE_STYLES } from "@/lib/fragmentFeedback"

function rounds(count: number): string {
  if (count === 1) return "1 runda"
  return count >= 2 && count <= 4 ? `${count} rundy` : `${count} rund`
}

function formatDay(day: string): string {
  return new Date(`${day}T12:00:00`).toLocaleDateString("pl-PL")
}

const iconButton =
  "rounded p-1 text-muted hover:bg-surface-alt hover:text-foreground disabled:opacity-30"

/**
 * The thesis at a glance: which parts exist, and where each one stands.
 * Mostly fills itself in as fragments arrive; adding one here is for a part
 * with a deadline, before anything was handed in.
 */
export default function PartMap({
  studentId,
  parts,
  onChange,
}: {
  studentId: string
  parts: PartEntry[]
  onChange: () => void
}) {
  const [name, setName] = useState("")
  const [dueOn, setDueOn] = useState("")
  const [error, setError] = useState<string | null>(null)

  async function run(change: () => Promise<unknown>): Promise<void> {
    setError(null)
    try {
      await change()
      onChange()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać zmiany")
    }
  }

  async function add(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    if (!name.trim()) return
    await run(() => addPart(studentId, name.trim(), dueOn || null))
    setName("")
    setDueOn("")
  }

  return (
    <div className="mb-6 rounded-xl border border-line bg-surface">
      {parts.length === 0 && (
        <p className="px-4 py-3 text-[13.5px] text-muted">
          Części pojawią się tu same, gdy dodasz pierwszy fragment.
        </p>
      )}
      {parts.map((entry, index) => (
        <div
          key={entry.id}
          data-testid="part-row"
          className="flex items-center gap-3 border-b border-line/60 px-4 py-2 text-[13.5px] last:border-none"
        >
          <span className="min-w-0 flex-1 truncate text-foreground">{entry.name}</span>
          {entry.due_on && (
            <span className="text-[12.5px] text-muted">do {formatDay(entry.due_on)}</span>
          )}
          <span className="w-16 text-[12.5px] text-muted">{rounds(entry.rounds)}</span>
          <span
            data-testid="part-state"
            className={`w-32 rounded-md px-2 py-0.5 text-center text-[12.5px] font-medium ${PART_STATE_STYLES[entry.state]}`}
          >
            {PART_STATE_LABELS[entry.state]}
          </span>
          <button
            type="button"
            aria-label={`Przesuń wyżej: ${entry.name}`}
            disabled={index === 0}
            onClick={() =>
              void run(() => updatePart(studentId, entry.id, { position: index }))
            }
            className={iconButton}
          >
            <IconArrowUp size={14} stroke={2} />
          </button>
          <button
            type="button"
            aria-label={`Przesuń niżej: ${entry.name}`}
            disabled={index === parts.length - 1}
            onClick={() =>
              void run(() => updatePart(studentId, entry.id, { position: index + 2 }))
            }
            className={iconButton}
          >
            <IconArrowDown size={14} stroke={2} />
          </button>
          {entry.rounds === 0 && (
            <button
              type="button"
              aria-label={`Usuń: ${entry.name}`}
              onClick={() => void run(() => deletePart(studentId, entry.id))}
              className={iconButton}
            >
              <IconTrash size={14} stroke={1.75} />
            </button>
          )}
        </div>
      ))}
      <form
        onSubmit={(event) => void add(event)}
        className="flex items-center gap-2 border-t border-line/60 px-4 py-2"
      >
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          aria-label="Nazwa nowej części"
          placeholder="Nowa część, np. Rozdział 3"
          className="min-w-0 flex-1 bg-transparent text-[13px] text-foreground focus:outline-none"
        />
        <input
          type="date"
          value={dueOn}
          onChange={(e) => setDueOn(e.target.value)}
          aria-label="Termin"
          className="bg-transparent text-[12.5px] text-muted focus:outline-none"
        />
        <button type="submit" aria-label="Dodaj część" className={iconButton}>
          <IconPlus size={15} stroke={2} />
        </button>
      </form>
      {error && (
        <p role="alert" className="px-4 pb-2 text-[13px] text-critical-text">
          {error}
        </p>
      )}
    </div>
  )
}
