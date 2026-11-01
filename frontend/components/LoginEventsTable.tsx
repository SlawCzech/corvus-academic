"use client"

import { useState } from "react"
import useSWR from "swr"
import { request } from "@/lib/api.client"

interface LoginEvent {
  id: string
  email: string
  ip_address: string
  user_agent: string
  success: boolean
  created_at: string
}

const fetcher = (url: string) =>
  request(url).then((r) => {
    if (!r.ok) throw new Error("Fetch failed")
    return r.json() as Promise<LoginEvent[]>
  })

export default function LoginEventsTable() {
  const { data: events, error } = useSWR<LoginEvent[]>("/api/admin/login-events", fetcher)
  const [filterEmail, setFilterEmail] = useState("")
  const [filterSuccess, setFilterSuccess] = useState<"all" | "true" | "false">("all")

  const filtered = events?.filter((e) => {
    const matchEmail = filterEmail === "" || e.email.toLowerCase().includes(filterEmail.toLowerCase())
    const matchSuccess =
      filterSuccess === "all" ||
      (filterSuccess === "true" ? e.success : !e.success)
    return matchEmail && matchSuccess
  })

  if (error) {
    return <p className="text-sm text-red-600">Błąd ładowania logów logowania.</p>
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="Filtruj po emailu…"
          value={filterEmail}
          onChange={(e) => setFilterEmail(e.target.value)}
          className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-gray-900"
        />
        <select
          value={filterSuccess}
          onChange={(e) => setFilterSuccess(e.target.value as "all" | "true" | "false")}
          className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-gray-900"
        >
          <option value="all">Wszystkie</option>
          <option value="true">Sukces</option>
          <option value="false">Porażka</option>
        </select>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-800">
              <th className="pb-2 font-medium text-gray-700 dark:text-gray-300">Email</th>
              <th className="pb-2 font-medium text-gray-700 dark:text-gray-300">Data</th>
              <th className="pb-2 font-medium text-gray-700 dark:text-gray-300">IP</th>
              <th className="pb-2 font-medium text-gray-700 dark:text-gray-300">User-Agent</th>
              <th className="pb-2 font-medium text-gray-700 dark:text-gray-300">Wynik</th>
            </tr>
          </thead>
          <tbody>
            {!events && (
              <tr>
                <td colSpan={5} className="py-6 text-center text-gray-400">
                  Ładowanie…
                </td>
              </tr>
            )}
            {filtered?.length === 0 && (
              <tr>
                <td colSpan={5} className="py-6 text-center text-gray-400">
                  Brak wyników.
                </td>
              </tr>
            )}
            {filtered?.map((event) => (
              <tr key={event.id} className="border-b border-gray-100 dark:border-gray-900">
                <td className="py-2.5 text-gray-900 dark:text-gray-100">{event.email}</td>
                <td className="py-2.5 text-gray-500 whitespace-nowrap">
                  {new Date(event.created_at).toLocaleString("pl-PL")}
                </td>
                <td className="py-2.5 font-mono text-[12px] text-gray-500">{event.ip_address}</td>
                <td className="py-2.5 max-w-[200px] truncate text-[12px] text-gray-400" title={event.user_agent}>
                  {event.user_agent}
                </td>
                <td className="py-2.5">
                  <span
                    className={`inline-block rounded px-2 py-0.5 text-[11px] font-medium ${
                      event.success
                        ? "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-400"
                        : "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400"
                    }`}
                  >
                    {event.success ? "OK" : "FAIL"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
