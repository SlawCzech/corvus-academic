"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import {
  IconPlus,
  IconUsers,
  IconBulbOff,
  IconLoader2,
  IconArrowRight,
  IconHandStop,
} from "@tabler/icons-react"
import InProgressActions from "@/components/InProgressActions"
import StudentForm from "@/components/students/StudentForm"
import { timeAgo } from "@/components/students/format"
import { fetcher } from "@/lib/api.client"
import type { DashboardSummary } from "@/lib/api.types"

function formatDay(day: string): string {
  return new Date(`${day}T12:00:00`).toLocaleDateString("pl-PL")
}

const ACTION_LABELS: Record<string, string> = {
  propose_topic: "propozycja tematu",
  defence_questions: "pytania na obronę",
  check_progress: "sprawdzenie postępu",
  evaluate_methodology: "ocena metodologii",
  draft_meeting_note: "szkic notatki",
  generate_review: "recenzja",
  verify_bibliography: "sprawdzenie bibliografii",
}

const STATUS_ACTIVITY_LABELS: Record<string, string> = {
  pending: "w kolejce",
  running: "w toku",
  awaiting_input: "czeka na Twój wybór uwag",
  completed: "gotowe",
  failed: "błąd",
  cancelled: "przerwana",
}

export default function DashboardPage() {
  const { data: summary, error, mutate } = useSWR<DashboardSummary>(
    "/api/dashboard/summary",
    fetcher,
  )
  const [showForm, setShowForm] = useState(false)
  const [showInProgress, setShowInProgress] = useState(false)

  return (
    <main className="px-12 py-10">
      <div className="mb-8 flex items-end justify-between">
        <div>
          <h1 className="text-[26px] font-semibold text-foreground">Dashboard</h1>
          <p className="mt-1.5 text-[13.5px] text-muted-strong">
            Przegląd studentów i ostatniej aktywności AI.
          </p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex h-10 items-center gap-1.5 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors"
        >
          <IconPlus size={15} stroke={2.25} />
          Nowy student
        </button>
      </div>

      {showForm && (
        <StudentForm
          onSaved={() => {
            void mutate()
            setShowForm(false)
          }}
          onCancel={() => setShowForm(false)}
        />
      )}

      {(summary?.awaiting_input ?? []).map((item) => (
        <div
          key={item.id}
          data-testid="awaiting-input"
          className="mb-4 flex items-center justify-between gap-4 rounded-xl border border-accent bg-accent-soft p-5"
        >
          <div className="flex items-center gap-3">
            <IconHandStop size={18} stroke={1.75} className="shrink-0 text-accent-hover" />
            <div>
              <span className="block text-[13px] font-semibold text-accent-hover">
                Czeka na Ciebie
              </span>
              <span className="text-[13.5px] text-foreground">
                <strong className="font-semibold">{item.student_name}</strong> —{" "}
                {ACTION_LABELS[item.action_type] ?? item.action_type}: uwagi są gotowe,
                wybierz, z których ma powstać recenzja.
              </span>
            </div>
          </div>
          <Link
            href={`/students/${item.student_id}?section=actions`}
            className="flex h-9 shrink-0 items-center rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors"
          >
            Wybierz uwagi
          </Link>
        </div>
      ))}

      <div className="mb-7 grid grid-cols-3 gap-4">
        <Link
          href="/students"
          className="group rounded-xl border border-line bg-surface p-5 transition-colors hover:border-accent"
        >
          <div className="mb-2 flex items-center gap-2 text-muted">
            <IconUsers size={15} stroke={1.75} />
            <span className="text-[12px]">Aktywni studenci</span>
            <IconArrowRight
              size={13}
              stroke={2}
              className="ml-auto opacity-0 transition-opacity group-hover:opacity-100"
            />
          </div>
          <span className="font-serif text-[28px] font-semibold text-foreground">
            {summary?.active_students ?? "—"}
          </span>
        </Link>
        <button
          type="button"
          aria-expanded={showInProgress}
          onClick={() => setShowInProgress((v) => !v)}
          className={`group rounded-xl border bg-surface p-5 text-left transition-colors hover:border-accent ${
            showInProgress ? "border-accent" : "border-line"
          }`}
        >
          <div className="mb-2 flex items-center gap-2 text-muted">
            <IconLoader2 size={15} stroke={1.75} />
            <span className="text-[12px]">Akcje AI w toku</span>
            <IconArrowRight
              size={13}
              stroke={2}
              className={`ml-auto transition-all ${
                showInProgress ? "rotate-90 opacity-100" : "opacity-0 group-hover:opacity-100"
              }`}
            />
          </div>
          <span className="font-serif text-[28px] font-semibold text-foreground">
            {summary?.actions_in_progress ?? "—"}
          </span>
          {summary && summary.awaiting_input.length > 0 && (
            <span className="ml-2 text-[12px] text-accent-hover">
              w tym {summary.awaiting_input.length} czeka na Ciebie
            </span>
          )}
        </button>
        <Link
          href="/students?topic=none"
          className="group rounded-xl border border-major-border bg-major-bg p-5 transition-colors hover:border-major-text"
        >
          <div className="mb-2 flex items-center gap-2 text-major-text">
            <IconBulbOff size={15} stroke={1.75} />
            <span className="text-[12px]">Bez ustalonego tematu</span>
            <IconArrowRight
              size={13}
              stroke={2}
              className="ml-auto opacity-0 transition-opacity group-hover:opacity-100"
            />
          </div>
          <span className="font-serif text-[28px] font-semibold text-major-text">
            {summary?.without_topic ?? "—"}
          </span>
        </Link>
      </div>

      {showInProgress && <InProgressActions onChange={() => void mutate()} />}

      {error && (
        <p className="text-[13px] text-critical-text">
          Nie udało się pobrać podsumowania.
        </p>
      )}

      {summary && summary.awaiting_feedback.length > 0 && (
        <div
          data-testid="awaiting-feedback"
          className="mb-4 rounded-xl border border-line bg-surface p-5"
        >
          <h2 className="mb-2 text-[13px] font-semibold text-foreground">
            Czeka na feedback
          </h2>
          {summary.awaiting_feedback.map((item) => (
            <Link
              key={item.fragment_id}
              href={`/students/${item.student_id}?section=timeline`}
              className="flex items-center justify-between border-b border-line/60 py-2.5 text-[13.5px] last:border-none hover:text-accent"
            >
              <span className="text-foreground">
                <strong className="font-semibold">{item.student_name}</strong> —{" "}
                {item.part_name}, runda {item.round_number}
              </span>
              <span className="text-muted">{formatDay(item.received_on)}</span>
            </Link>
          ))}
        </div>
      )}

      {summary && summary.overdue_parts.length > 0 && (
        <div
          data-testid="overdue-parts"
          className="mb-4 rounded-xl border border-line bg-surface p-5"
        >
          <h2 className="mb-2 text-[13px] font-semibold text-foreground">Po terminie</h2>
          {summary.overdue_parts.map((item) => (
            <Link
              key={item.part_id}
              href={`/students/${item.student_id}?section=timeline`}
              className="flex items-center justify-between border-b border-line/60 py-2.5 text-[13.5px] last:border-none hover:text-accent"
            >
              <span className="text-foreground">
                <strong className="font-semibold">{item.student_name}</strong> —{" "}
                {item.part_name}
              </span>
              <span className="text-muted">{formatDay(item.due_on)}</span>
            </Link>
          ))}
        </div>
      )}

      {summary && (
        <div className="rounded-xl border border-line bg-surface p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-[13px] font-semibold text-foreground">
              Ostatnia aktywność
            </h2>
            <Link
              href="/students"
              className="flex items-center gap-1 text-[12.5px] text-muted hover:text-accent"
            >
              Wszyscy studenci
              <IconArrowRight size={13} stroke={2} />
            </Link>
          </div>
          {summary.recent_activity.length === 0 ? (
            <p className="text-[13.5px] text-muted">
              Jeszcze nic się nie wydarzyło — uruchom akcję AI u któregoś ze
              studentów.
            </p>
          ) : (
            <div className="flex flex-col">
              {summary.recent_activity.map((a, i) => (
                <Link
                  key={`${a.student_id}-${a.updated_at}-${i}`}
                  href={
                    a.status === "awaiting_input" || a.status === "running" || a.status === "pending"
                      ? `/students/${a.student_id}?section=actions`
                      : `/students/${a.student_id}`
                  }
                  className="flex items-center justify-between border-b border-line/60 py-2.5 text-[13.5px] last:border-none hover:text-accent"
                >
                  <span className="text-foreground">
                    <strong className="font-semibold">{a.student_name}</strong> —{" "}
                    {ACTION_LABELS[a.action_type] ?? a.action_type}
                    {" · "}
                    {STATUS_ACTIVITY_LABELS[a.status] ?? a.status}
                  </span>
                  <span className="text-muted">{timeAgo(a.updated_at)}</span>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </main>
  )
}
