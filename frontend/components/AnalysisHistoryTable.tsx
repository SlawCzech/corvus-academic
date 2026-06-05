"use client"

import Link from "next/link"
import useSWR from "swr"

interface AnalysisRecord {
  id: string
  task_id: string
  thesis_title?: string
  thesis_type: string
  status: string
  created_at: string
}

const fetcher = (url: string) =>
  fetch(url).then((r) => {
    if (!r.ok) throw new Error("Fetch failed")
    return r.json() as Promise<AnalysisRecord[]>
  })

const STATUS_LABELS: Record<string, string> = {
  pending: "Oczekuje",
  processing: "W toku",
  done: "Gotowe",
  error: "Błąd",
}

export default function AnalysisHistoryTable() {
  const { data: analyses, error } = useSWR<AnalysisRecord[]>("/api/analysis", fetcher)

  if (error) {
    return <p className="text-sm text-red-600">Błąd ładowania historii analiz.</p>
  }

  return (
    <table className="w-full text-left text-sm">
      <thead>
        <tr className="border-b border-gray-200 dark:border-gray-800">
          <th className="pb-2 font-medium text-gray-700 dark:text-gray-300">Tytuł</th>
          <th className="pb-2 font-medium text-gray-700 dark:text-gray-300">Typ</th>
          <th className="pb-2 font-medium text-gray-700 dark:text-gray-300">Data</th>
          <th className="pb-2 font-medium text-gray-700 dark:text-gray-300">Status</th>
          <th className="pb-2 font-medium text-gray-700 dark:text-gray-300"></th>
        </tr>
      </thead>
      <tbody>
        {!analyses && (
          <tr>
            <td colSpan={5} className="py-6 text-center text-gray-400">
              Ładowanie…
            </td>
          </tr>
        )}
        {analyses?.length === 0 && (
          <tr>
            <td colSpan={5} className="py-6 text-center text-gray-400">
              Brak analiz.
            </td>
          </tr>
        )}
        {analyses?.map((a) => (
          <tr key={a.id} className="border-b border-gray-100 dark:border-gray-900">
            <td className="py-3 text-gray-900 dark:text-gray-100">
              {a.thesis_title ?? <span className="text-gray-400 italic">Bez tytułu</span>}
            </td>
            <td className="py-3 text-gray-600 dark:text-gray-400 capitalize">{a.thesis_type}</td>
            <td className="py-3 text-gray-500 whitespace-nowrap">
              {new Date(a.created_at).toLocaleDateString("pl-PL")}
            </td>
            <td className="py-3">
              <span
                className={`inline-block rounded px-2 py-0.5 text-[11px] font-medium ${
                  a.status === "done"
                    ? "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-400"
                    : a.status === "error"
                      ? "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400"
                      : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
                }`}
              >
                {STATUS_LABELS[a.status] ?? a.status}
              </span>
            </td>
            <td className="py-3 text-right">
              {a.status === "done" && (
                <Link
                  href={`/analysis?task_id=${a.task_id}`}
                  className="text-[12px] text-gray-600 dark:text-gray-400 hover:underline"
                >
                  Zobacz wynik
                </Link>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
