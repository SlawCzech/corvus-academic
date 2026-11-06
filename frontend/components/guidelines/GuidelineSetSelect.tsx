"use client"

import { useEffect, useState } from "react"
import useSWR from "swr"
import { useHomeUniversity } from "@/hooks/useHomeUniversity"
import { fetcher } from "@/lib/api.client"
import type { GuidelineSet } from "@/lib/api.types"

const OTHER = "__other__"

interface Props {
  thesisType: string
  /** The chosen set's id, or "" before anything is chosen. */
  value: string
  onChange: (setId: string) => void
  disabled?: boolean
  className?: string
  /**
   * Pick the promoter's university's set on its own when it is the only one
   * for this kind of thesis — for a form that is about to be sent anyway.
   */
  autoSelect?: boolean
}

/**
 * The guideline sets in force for one kind of thesis.
 *
 * Every thesis is judged against a university's rules and Corvus has none of
 * its own (ADR 0023), so there is no "none" to pick: before a choice the
 * select shows a placeholder, and a form using it requires a value.
 *
 * A promoter with a home university sees its sets; the others are one
 * choice away, under "Inna uczelnia…", for a thesis from elsewhere.
 */
export default function GuidelineSetSelect({
  thesisType,
  value,
  onChange,
  disabled,
  className,
  autoSelect,
}: Props) {
  const { data: sets } = useSWR<GuidelineSet[]>(
    `/api/guidelines/sets?thesis_type=${thesisType}`,
    fetcher,
  )
  const home = useHomeUniversity()
  const [showAll, setShowAll] = useState(false)

  const available = (Array.isArray(sets) ? sets : []).filter((s) => s.current !== null)
  const homeSets = home ? available.filter((s) => s.university.id === home) : available
  const chosenElsewhere =
    value !== "" && !homeSets.some((s) => s.id === value) && available.some((s) => s.id === value)
  const everything = showAll || !home || chosenElsewhere || homeSets.length === 0
  const shown = everything ? available : homeSets
  const known = shown.some((s) => s.id === value)
  const onlyHomeSet = home && homeSets.length === 1 ? homeSets[0].id : null

  useEffect(() => {
    if (autoSelect && value === "" && onlyHomeSet) onChange(onlyHomeSet)
  }, [autoSelect, value, onlyHomeSet, onChange])

  return (
    <select
      aria-label="Zestaw wytycznych"
      required
      value={known ? value : ""}
      disabled={disabled || sets === undefined || home === undefined}
      onChange={(e) => {
        if (e.target.value === OTHER) setShowAll(true)
        else onChange(e.target.value)
      }}
      className={className}
    >
      <option value="" disabled>
        {sets !== undefined && available.length === 0
          ? "Brak wytycznych dla tego typu pracy"
          : "Wybierz wytyczne uczelni"}
      </option>
      {shown.map((s) => (
        <option key={s.id} value={s.id}>
          {s.university.short_name} — {s.name}
        </option>
      ))}
      {!everything && available.length > homeSets.length && (
        <option value={OTHER}>Inna uczelnia…</option>
      )}
    </select>
  )
}
