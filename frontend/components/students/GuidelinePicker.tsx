"use client"

import Link from "next/link"
import { useState } from "react"
import useSWR from "swr"
import GuidelineSetSelect from "@/components/guidelines/GuidelineSetSelect"
import { fetcher, updateStudent } from "@/lib/api.client"
import type { GuidelineSet, Student } from "@/lib/api.types"

interface Props {
  student: Student
  onChange: (student: Student) => void
}

/**
 * Which university requirements this thesis is judged against.
 *
 * Only sets for the student's own kind of thesis are offered. There is no
 * built-in fallback (ADR 0024): a student without a set — one added before
 * sets were required, or whose thesis type changed — gets a review only
 * once a set is chosen here.
 */
export default function GuidelinePicker({ student, onChange }: Props) {
  const { data: sets } = useSWR<GuidelineSet[]>(
    `/api/guidelines/sets?thesis_type=${student.thesis_type}`,
    fetcher,
  )
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const chosen = (Array.isArray(sets) ? sets : []).find(
    (s) => s.id === student.guideline_set_id && s.current !== null,
  )

  async function choose(setId: string): Promise<void> {
    if (!setId) return
    setSaving(true)
    setError(null)
    try {
      onChange(await updateStudent(student.id, { guideline_set_id: setId }))
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać wyboru")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="rounded-xl border border-line bg-surface p-5">
      <h3 className="mb-3 text-[11.5px] font-semibold uppercase tracking-wide text-muted">
        Wytyczne uczelni
      </h3>
      <GuidelineSetSelect
        thesisType={student.thesis_type}
        value={student.guideline_set_id ?? ""}
        onChange={(setId) => void choose(setId)}
        disabled={saving}
        className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[13.5px] text-foreground focus:border-accent focus:outline-none"
      />
      {(!student.guideline_set_id || (Array.isArray(sets) && !chosen)) && (
        <p data-testid="missing-guidelines" className="mt-2.5 text-[12.5px] text-major-text">
          {student.guideline_set_id
            ? "Wybrany zestaw wytycznych został usunięty. Wybierz inny, zanim pójdzie recenzja."
            : "Wybierz wytyczne uczelni. Bez nich recenzja i ocena metodologii się nie uruchomią: Corvus nie ma własnych wymogów."}
        </p>
      )}
      {chosen?.current && (
        <p className="mt-2.5 text-[12.5px] text-muted">
          Recenzja i ocena metodologii według wersji {chosen.current.version_no}.{" "}
          <Link href={`/guidelines/${chosen.current.id}`} className="text-accent hover:underline">
            Zobacz wytyczne
          </Link>
        </p>
      )}
      {error && (
        <p role="alert" className="mt-2 text-[13px] text-critical-text">
          {error}
        </p>
      )}
    </div>
  )
}
