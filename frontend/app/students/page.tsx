"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import {
  IconSearch,
  IconPlus,
  IconUsers,
  IconBulbOff,
  IconLoader2,
} from "@tabler/icons-react"
import StudentForm from "@/components/students/StudentForm"
import { fetcher } from "@/lib/api.client"
import type { DashboardSummary, Student } from "@/lib/api.types"

const STATUS_LABELS: Record<string, string> = {
  active: "Aktywny",
  graduated: "Obroniony",
  archived: "Archiwalny",
}

const STATUS_STYLES: Record<string, string> = {
  active: "bg-success-bg text-success-text",
  graduated: "bg-info-bg text-info-text",
  archived: "bg-surface-alt text-muted-strong",
}

const ACTION_LABELS: Record<string, string> = {
  propose_topic: "propozycja tematu",
  defence_questions: "pytania na obronę",
  check_progress: "sprawdzenie postępu",
  evaluate_methodology: "ocena metodologii",
  draft_meeting_note: "szkic notatki",
  generate_review: "recenzja",
}

const STATUS_ACTIVITY_LABELS: Record<string, string> = {
  pending: "w kolejce",
  running: "w toku",
  completed: "gotowe",
  failed: "błąd",
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const hours = Math.floor(diffMs / 3_600_000)
  if (hours < 1) return "przed chwilą"
  if (hours < 24) return `${hours} godz. temu`
  const days = Math.floor(hours / 24)
  if (days < 14) return `${days} dni temu`
  return new Date(iso).toLocaleDateString("pl-PL")
}

export default function StudentsPage() {
  const { data: students, error, mutate } = useSWR<Student[]>(
    "/api/students",
    fetcher,
  )
  const { data: summary } = useSWR<DashboardSummary>(
    "/api/dashboard/summary",
    fetcher,
  )

  const [showForm, setShowForm] = useState(false)
  const [query, setQuery] = useState("")

  const filtered = useMemo(() => {
    if (!students) return students
    const q = query.trim().toLowerCase()
    if (!q) return students
    return students.filter(
      (s) =>
        s.full_name.toLowerCase().includes(q) ||
        s.field_of_study.toLowerCase().includes(q) ||
        (s.current_topic ?? "").toLowerCase().includes(q),
    )
  }, [students, query])

  return (
    <main className="px-12 py-10">
      <div className="mb-8 flex items-end justify-between">
        <div>
          <h1 className="text-[26px] font-semibold text-foreground">Dashboard</h1>
          <p className="mt-1.5 text-[13.5px] text-muted-strong">
            Przegląd studentów i ostatniej aktywności AI.
          </p>
        </div>
        <div className="flex gap-2.5">
          <div className="relative">
            <IconSearch
              size={15}
              stroke={2}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Szukaj studenta…"
              className="h-10 w-56 rounded-lg border border-line bg-surface py-0 pl-8 pr-3 text-[13.5px] text-foreground focus:border-accent focus:outline-none"
            />
          </div>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="flex h-10 items-center gap-1.5 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors"
          >
            <IconPlus size={15} stroke={2.25} />
            Nowy student
          </button>
        </div>
      </div>

      {showForm && (
        <StudentForm
          onCreated={() => {
            void mutate()
            setShowForm(false)
          }}
          onCancel={() => setShowForm(false)}
        />
      )}

      <div className="mb-7 grid grid-cols-3 gap-4">
        <div className="rounded-xl border border-line bg-surface p-5">
          <div className="mb-2 flex items-center gap-2 text-muted">
            <IconUsers size={15} stroke={1.75} />
            <span className="text-[12px]">Aktywni studenci</span>
          </div>
          <span className="font-serif text-[28px] font-semibold text-foreground">
            {summary?.active_students ?? "—"}
          </span>
        </div>
        <div className="rounded-xl border border-line bg-surface p-5">
          <div className="mb-2 flex items-center gap-2 text-muted">
            <IconLoader2 size={15} stroke={1.75} />
            <span className="text-[12px]">Akcje AI w toku</span>
          </div>
          <span className="font-serif text-[28px] font-semibold text-foreground">
            {summary?.actions_in_progress ?? "—"}
          </span>
        </div>
        <div className="rounded-xl border border-major-border bg-major-bg p-5">
          <div className="mb-2 flex items-center gap-2 text-major-text">
            <IconBulbOff size={15} stroke={1.75} />
            <span className="text-[12px]">Bez ustalonego tematu</span>
          </div>
          <span className="font-serif text-[28px] font-semibold text-major-text">
            {summary?.without_topic ?? "—"}
          </span>
        </div>
      </div>

      {summary && summary.recent_activity.length > 0 && (
        <div className="mb-7 rounded-xl border border-line bg-surface p-5">
          <h2 className="mb-3 text-[13px] font-semibold text-foreground">
            Ostatnia aktywność
          </h2>
          <div className="flex flex-col">
            {summary.recent_activity.map((a, i) => (
              <div
                key={`${a.student_id}-${a.updated_at}-${i}`}
                className="flex items-center justify-between border-b border-line/60 py-2.5 text-[13.5px] last:border-none"
              >
                <span className="text-foreground">
                  <strong className="font-semibold">{a.student_name}</strong> —{" "}
                  {ACTION_LABELS[a.action_type] ?? a.action_type}
                  {" · "}
                  {STATUS_ACTIVITY_LABELS[a.status] ?? a.status}
                </span>
                <span className="text-muted">{timeAgo(a.updated_at)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <p className="text-[13px] text-critical-text">Nie udało się pobrać listy.</p>
      )}

      {filtered && filtered.length === 0 && (
        <p className="text-[13.5px] text-muted">
          {query ? "Brak wyników." : "Nie masz jeszcze żadnych studentów."}
        </p>
      )}

      {filtered && filtered.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-line bg-surface">
          <table className="w-full text-left text-[13.5px]">
            <thead>
              <tr className="border-b border-line text-[11.5px] uppercase tracking-wide text-muted">
                <th className="py-2.5 pl-6 font-semibold">Student</th>
                <th className="py-2.5 font-semibold">Temat</th>
                <th className="py-2.5 font-semibold">Status</th>
                <th className="py-2.5 pr-6 font-semibold">Ostatnia aktywność</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => (
                <tr key={s.id} className="border-b border-line/60 last:border-none">
                  <td className="py-3.5 pl-6">
                    <Link
                      href={`/students/${s.id}`}
                      className="font-semibold text-foreground hover:text-accent"
                    >
                      {s.full_name}
                    </Link>
                    <span className="block text-[12px] text-muted">
                      {s.field_of_study}
                    </span>
                  </td>
                  <td className="py-3.5 pr-4 text-muted-strong">
                    {s.current_topic ?? (
                      <span className="italic text-muted">brak tematu</span>
                    )}
                  </td>
                  <td className="py-3.5">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[12px] font-medium ${
                        STATUS_STYLES[s.status] ?? "bg-surface-alt text-muted-strong"
                      }`}
                    >
                      {STATUS_LABELS[s.status] ?? s.status}
                    </span>
                  </td>
                  <td className="py-3.5 pr-6 text-muted">{timeAgo(s.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  )
}
