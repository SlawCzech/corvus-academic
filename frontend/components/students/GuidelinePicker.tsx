"use client"

import Link from "next/link"
import { useState } from "react"
import useSWR from "swr"
import { fetcher, updateStudent } from "@/lib/api.client"
import type { GuidelineSet, Student } from "@/lib/api.types"

interface Props {
  student: Student
  onChange: (student: Student) => void
}

/**
 * Which university requirements this thesis is judged against.
 *
 * Only sets for the student's own kind of thesis are offered. With none
 * chosen, the review falls back to the agent's built-in requirements.
 */
export default function GuidelinePicker({ student, onChange }: Props) {
  const { data: sets } = useSWR<GuidelineSet[]>(
    `/api/guidelines/sets?thesis_type=${student.thesis_type}`,
    fetcher,
  )
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const available = (sets ?? []).filter((s) => s.current !== null)
  const chosen = available.find((s) => s.id === student.guideline_set_id)

  async function choose(setId: string): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      onChange(await updateStudent(student.id, { guideline_set_id: setId || null }))
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
      <select
        aria-label="Zestaw wytycznych"
        value={student.guideline_set_id ?? ""}
        disabled={saving || sets === undefined}
        onChange={(e) => void choose(e.target.value)}
        className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[13.5px] text-foreground focus:border-accent focus:outline-none"
      >
        <option value="">Domyślne wymogi Corvusa</option>
        {available.map((s) => (
          <option key={s.id} value={s.id}>
            {s.university.short_name} — {s.name}
          </option>
        ))}
      </select>
      {!student.guideline_set_id && (
        <p data-testid="default-guidelines" className="mt-2.5 text-[12.5px] text-major-text">
          Uwaga: to ogólne wymogi wbudowane w Corvusa, nie wytyczne Twojej uczelni. Recenzja i
          ocena metodologii nie sprawdzą zgodności z regulaminem uczelni.
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
