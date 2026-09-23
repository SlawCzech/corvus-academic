import type { GuidelineVersionStatus, Thresholds } from "@/lib/api.types"

export const THESIS_TYPE_LABELS: Record<string, string> = {
  bachelor: "Licencjacka",
  master_article: "Magisterska (artykuł)",
}

export const VERSION_STATUS_LABELS: Record<GuidelineVersionStatus, string> = {
  draft: "szkic",
  published: "obowiązuje",
  superseded: "zastąpiona",
}

export const VERSION_STATUS_STYLES: Record<GuidelineVersionStatus, string> = {
  draft: "bg-major-bg text-major-text",
  published: "bg-success-bg text-success-text",
  superseded: "bg-surface-alt text-muted-strong",
}

/** The numbers the regulation sets, in the order a promoter reads them. */
export const THRESHOLD_FIELDS: { key: keyof Thresholds; label: string }[] = [
  { key: "min_sources", label: "Minimalna liczba źródeł" },
  { key: "min_foreign_sources", label: "W tym obcojęzycznych, minimum" },
  { key: "min_body_chars", label: "Objętość pracy, minimum (znaki)" },
  { key: "max_body_chars", label: "Objętość pracy, maksimum (znaki)" },
]

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })
}
