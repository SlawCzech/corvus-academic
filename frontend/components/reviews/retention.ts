function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })
}

/** What happens to the thesis of a one-off review: the results outlive it. */
export function retentionNote(purgedAt: string | null, dueAt: string | null): string {
  if (purgedAt) return "Tekst pracy usunięty"
  return dueAt ? `Tekst pracy do ${formatDate(dueAt)}` : ""
}
