"use client"

import useSWR from "swr"
import { fetcher } from "@/lib/api.client"
import type { GuidelineSet } from "@/lib/api.types"

interface Props {
  thesisType: string
  /** The chosen set's id, or "" before anything is chosen. */
  value: string
  onChange: (setId: string) => void
  disabled?: boolean
  className?: string
}

/**
 * The guideline sets in force for one kind of thesis.
 *
 * Every thesis is judged against a university's rules and Corvus has none of
 * its own (ADR 0023), so there is no "none" to pick: before a choice the
 * select shows a placeholder, and a form using it requires a value.
 */
export default function GuidelineSetSelect({
  thesisType,
  value,
  onChange,
  disabled,
  className,
}: Props) {
  const { data: sets } = useSWR<GuidelineSet[]>(
    `/api/guidelines/sets?thesis_type=${thesisType}`,
    fetcher,
  )
  const available = (Array.isArray(sets) ? sets : []).filter((s) => s.current !== null)
  const known = available.some((s) => s.id === value)

  return (
    <select
      aria-label="Zestaw wytycznych"
      required
      value={known ? value : ""}
      disabled={disabled || sets === undefined}
      onChange={(e) => onChange(e.target.value)}
      className={className}
    >
      <option value="" disabled>
        {sets !== undefined && available.length === 0
          ? "Brak wytycznych dla tego typu pracy"
          : "Wybierz wytyczne uczelni"}
      </option>
      {available.map((s) => (
        <option key={s.id} value={s.id}>
          {s.university.short_name} — {s.name}
        </option>
      ))}
    </select>
  )
}
