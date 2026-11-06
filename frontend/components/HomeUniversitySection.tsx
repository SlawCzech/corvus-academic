"use client"

import { useState } from "react"
import useSWR, { useSWRConfig } from "swr"
import { HOME_UNIVERSITY_KEY, useHomeUniversity } from "@/hooks/useHomeUniversity"
import { fetcher, setHomeUniversity } from "@/lib/api.client"
import type { University } from "@/lib/api.types"

/** "Moja uczelnia": whose guidelines a promoter sees first. */
export default function HomeUniversitySection() {
  const { data: universities } = useSWR<University[]>("/api/guidelines/universities", fetcher)
  const home = useHomeUniversity()
  const { mutate } = useSWRConfig()
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  async function choose(id: string): Promise<void> {
    setError(null)
    setSaved(false)
    try {
      await mutate(HOME_UNIVERSITY_KEY, await setHomeUniversity(id || null), {
        revalidate: false,
      })
      setSaved(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać")
    }
  }

  return (
    <div>
      <p className="mb-3 text-[13px] text-muted">
        Przy studentach i recenzjach zobaczysz najpierw wytyczne tej uczelni. Inne są pod
        „Inna uczelnia…”.
      </p>
      <select
        aria-label="Moja uczelnia"
        value={home ?? ""}
        disabled={home === undefined || universities === undefined}
        onChange={(e) => void choose(e.target.value)}
        className="w-full max-w-sm rounded-lg border border-line bg-surface px-3 py-1.5 text-[14px] text-foreground focus:border-accent focus:outline-none"
      >
        <option value="">Nie wybrano — pokazuj wszystkie</option>
        {(universities ?? []).map((u) => (
          <option key={u.id} value={u.id}>
            {u.name}
          </option>
        ))}
      </select>
      {saved && <span className="ml-3 text-[12.5px] text-success-text">Zapisano</span>}
      {error && (
        <p role="alert" className="mt-2 text-[13px] text-critical-text">
          {error}
        </p>
      )}
    </div>
  )
}
