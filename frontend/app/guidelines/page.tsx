"use client"

import Link from "next/link"
import { useState } from "react"
import useSWR from "swr"
import { useHomeUniversity } from "@/hooks/useHomeUniversity"
import { fetcher } from "@/lib/api.client"
import type { GuidelineSet } from "@/lib/api.types"
import { THESIS_TYPE_LABELS, formatDate } from "@/components/guidelines/format"

/**
 * The catalog as a promoter sees it: every set with a version in force —
 * their own university's, when they have set one, and the rest on request.
 */
export default function GuidelinesPage() {
  const { data: sets, error } = useSWR<GuidelineSet[]>("/api/guidelines/sets", fetcher)
  const home = useHomeUniversity()
  const [showAll, setShowAll] = useState(false)

  const published = (sets ?? []).filter((s) => s.current !== null)
  const own = home ? published.filter((s) => s.university.id === home) : published
  const narrowed = Boolean(home) && !showAll && own.length > 0
  const byUniversity = new Map<string, GuidelineSet[]>()
  for (const set of narrowed ? own : published) {
    const key = set.university.name
    byUniversity.set(key, [...(byUniversity.get(key) ?? []), set])
  }

  return (
    <main className="mx-auto max-w-4xl px-8 py-10">
      <h1 className="mb-2 font-serif text-[26px] font-semibold text-foreground">
        Wytyczne uczelni
      </h1>
      <p className="mb-8 text-[13.5px] text-muted">
        Wymogi, według których Corvus ocenia prace. Zestaw dla studenta wybierasz w jego
        przeglądzie.
      </p>

      {error && (
        <p className="text-[13px] text-critical-text">Nie udało się pobrać wytycznych.</p>
      )}
      {sets && byUniversity.size === 0 && (
        <p className="text-[13.5px] text-muted">Katalog jest jeszcze pusty.</p>
      )}

      {narrowed && published.length > own.length && (
        <button
          type="button"
          onClick={() => setShowAll(true)}
          className="mb-6 text-[13px] text-accent hover:underline"
        >
          Pokaż też inne uczelnie
        </button>
      )}

      {[...byUniversity.entries()].map(([university, universitySets]) => (
        <section key={university} className="mb-6">
          <h2 className="mb-3 text-[15px] font-semibold text-foreground">{university}</h2>
          <div className="rounded-xl border border-line bg-surface">
            {universitySets.map((set, i) => (
              <Link
                key={set.id}
                href={`/guidelines/${set.current!.id}`}
                className={`flex items-center justify-between px-5 py-3.5 text-[13.5px] hover:bg-surface-alt ${
                  i > 0 ? "border-t border-line/60" : ""
                }`}
              >
                <span>
                  <span className="block font-medium text-foreground">{set.name}</span>
                  <span className="text-[12.5px] text-muted">
                    {THESIS_TYPE_LABELS[set.thesis_type] ?? set.thesis_type}
                  </span>
                </span>
                <span className="text-right text-[12.5px] text-muted">
                  wersja {set.current!.version_no}
                  {set.current!.effective_from
                    ? ` · od ${formatDate(set.current!.effective_from)}`
                    : set.current!.published_at
                      ? ` · opublikowana ${formatDate(set.current!.published_at)}`
                      : ""}
                </span>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </main>
  )
}
