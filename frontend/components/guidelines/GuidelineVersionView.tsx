"use client"

import Link from "next/link"
import useSWR from "swr"
import { fetcher, guidelineSourceUrl } from "@/lib/api.client"
import type { GuidelineSetDetail, GuidelineVersion } from "@/lib/api.types"
import RubricView from "@/components/guidelines/RubricView"
import {
  THESIS_TYPE_LABELS,
  THRESHOLD_FIELDS,
  VERSION_STATUS_LABELS,
  VERSION_STATUS_STYLES,
  formatDate,
} from "@/components/guidelines/format"

/**
 * One version of a guideline set, as a promoter reads it: what it applies to,
 * the numbers it sets (the only place they live), the rubric by section with
 * which action reads which, the original regulation to check it against, and
 * the versions before it.
 */
export default function GuidelineVersionView({ versionId }: { versionId: string }) {
  const { data: version, error } = useSWR<GuidelineVersion>(
    `/api/guidelines/versions/${versionId}`,
    fetcher,
  )
  const { data: set } = useSWR<GuidelineSetDetail>(
    version ? `/api/guidelines/sets/${version.set_id}` : null,
    fetcher,
  )

  if (error) {
    return <p className="text-[13px] text-critical-text">Nie znaleziono tej wersji wytycznych.</p>
  }
  if (!version) {
    return <p className="text-[13px] text-muted">Wczytywanie…</p>
  }

  const thresholds = THRESHOLD_FIELDS.filter(({ key }) => version.thresholds[key] != null)

  return (
    <div>
      <p className="mb-1 text-[12.5px] text-muted">
        <Link href="/guidelines" className="hover:underline">
          Wytyczne
        </Link>{" "}
        / {version.university.short_name}
      </p>
      <h1 className="mb-2 font-serif text-[26px] font-semibold text-foreground">
        {version.set_name}
      </h1>
      <div className="mb-8 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-muted">
        <span>{version.university.name}</span>
        <span>· {THESIS_TYPE_LABELS[version.thesis_type] ?? version.thesis_type}</span>
        <span>· wersja {version.version_no}</span>
        <span
          className={`rounded-md px-1.5 py-0.5 text-[11.5px] font-semibold ${VERSION_STATUS_STYLES[version.status]}`}
        >
          {VERSION_STATUS_LABELS[version.status]}
        </span>
        {version.effective_from && <span>· obowiązuje od {formatDate(version.effective_from)}</span>}
        {version.published_at && <span>· opublikowana {formatDate(version.published_at)}</span>}
      </div>

      <div className="mb-6 grid grid-cols-2 gap-5">
        <section className="rounded-xl border border-line bg-surface p-5">
          <h2 className="mb-3 text-[11.5px] font-semibold uppercase tracking-wide text-muted">
            Progi liczbowe
          </h2>
          {thresholds.length === 0 ? (
            <p className="text-[13.5px] italic text-muted">Ta wersja nie ustala progów.</p>
          ) : (
            <table className="w-full text-[13.5px]">
              <tbody>
                {thresholds.map(({ key, label }) => (
                  <tr key={key} className="border-b border-line/60 last:border-none">
                    <td className="py-1.5 text-muted-strong">{label}</td>
                    <td className="py-1.5 text-right font-semibold text-foreground">
                      {version.thresholds[key]?.toLocaleString("pl-PL")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="rounded-xl border border-line bg-surface p-5">
          <h2 className="mb-3 text-[11.5px] font-semibold uppercase tracking-wide text-muted">
            Dokument źródłowy
          </h2>
          {version.source ? (
            <>
              <p className="text-[13.5px] text-foreground">{version.source.filename}</p>
              <p className="mt-1 break-all font-mono text-[11px] text-muted">
                SHA-256 {version.source.sha256}
              </p>
              {version.source.downloadable && (
                <a
                  href={guidelineSourceUrl(version.id)}
                  className="mt-3 inline-block text-[13px] font-medium text-accent hover:underline"
                >
                  Pobierz oryginał
                </a>
              )}
            </>
          ) : (
            <p className="text-[13.5px] italic text-muted">
              Do tej wersji nie dołączono oryginału zarządzenia.
            </p>
          )}
        </section>
      </div>

      <div className="mb-6">
        <RubricView rubric={version.rubric_md} />
      </div>

      {set && set.versions.length > 1 && (
        <section className="rounded-xl border border-line bg-surface p-5">
          <h2 className="mb-3 text-[11.5px] font-semibold uppercase tracking-wide text-muted">
            Historia wersji
          </h2>
          <ul className="text-[13.5px]">
            {set.versions.map((v) => (
              <li key={v.id} className="flex justify-between border-b border-line/60 py-1.5 last:border-none">
                {v.id === version.id ? (
                  <span className="font-semibold text-foreground">Wersja {v.version_no}</span>
                ) : (
                  <Link href={`/guidelines/${v.id}`} className="text-accent hover:underline">
                    Wersja {v.version_no}
                  </Link>
                )}
                <span className="text-muted">
                  {VERSION_STATUS_LABELS[v.status]}
                  {v.published_at ? ` · ${formatDate(v.published_at)}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
