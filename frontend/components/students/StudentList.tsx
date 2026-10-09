"use client"

import { useState } from "react"
import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { IconSearch, IconPlus, IconTrash, IconX } from "@tabler/icons-react"
import DeleteStudentConfirm from "@/components/students/DeleteStudentConfirm"
import DemoStudentsOffer from "@/components/students/DemoStudentsOffer"
import StatusSelect from "@/components/students/StatusSelect"
import StudentForm from "@/components/students/StudentForm"
import { timeAgo } from "@/components/students/format"
import { fetcher } from "@/lib/api.client"
import type { Student, StudentStatus } from "@/lib/api.types"

type StatusFilter = StudentStatus | "all"

const STATUS_TABS: { key: StatusFilter; label: string }[] = [
  { key: "active", label: "Aktywni" },
  { key: "graduated", label: "Obronieni" },
  { key: "archived", label: "Archiwalni" },
  { key: "all", label: "Wszyscy" },
]

function parseStatus(value: string | null): StatusFilter {
  return STATUS_TABS.some((t) => t.key === value) ? (value as StatusFilter) : "active"
}

/**
 * The promoter's roster. Status and "no topic" live in the URL so the
 * dashboard tiles can link straight into a filtered view.
 */
export default function StudentList() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const status = parseStatus(searchParams.get("status"))
  const withoutTopic = searchParams.get("topic") === "none"

  const { data: students, error, mutate } = useSWR<Student[]>(
    "/api/students",
    fetcher,
  )

  const [showForm, setShowForm] = useState(false)
  const [query, setQuery] = useState("")
  const [deleting, setDeleting] = useState<Student | null>(null)

  function replaceStudent(next: Student): void {
    void mutate((list) => list?.map((s) => (s.id === next.id ? next : s)), {
      revalidate: false,
    })
  }

  function setFilters(next: { status?: StatusFilter; withoutTopic?: boolean }): void {
    const params = new URLSearchParams(searchParams.toString())
    const nextStatus = next.status ?? status
    const nextTopic = next.withoutTopic ?? withoutTopic
    if (nextStatus === "active") params.delete("status")
    else params.set("status", nextStatus)
    if (nextTopic) params.set("topic", "none")
    else params.delete("topic")
    const qs = params.toString()
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false })
  }

  const counts: Record<StatusFilter, number> = {
    active: 0,
    graduated: 0,
    archived: 0,
    all: 0,
  }
  for (const s of students ?? []) {
    counts[s.status] += 1
    counts.all += 1
  }

  const q = query.trim().toLowerCase()
  const filtered = students?.filter(
    (s) =>
      (status === "all" || s.status === status) &&
      (!withoutTopic || s.current_topic === null) &&
      (!q ||
        s.full_name.toLowerCase().includes(q) ||
        s.field_of_study.toLowerCase().includes(q) ||
        (s.current_topic ?? "").toLowerCase().includes(q)),
  )

  const narrowed = q !== "" || withoutTopic

  return (
    <main className="px-12 py-10">
      <div className="mb-8 flex items-end justify-between">
        <div>
          <h1 className="text-[26px] font-semibold text-foreground">Studenci</h1>
          <p className="mt-1.5 text-[13.5px] text-muted-strong">
            Twoi dyplomanci — wejdź w studenta, żeby uruchomić akcje AI, dodać
            wersję pracy lub notatkę.
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
          onSaved={() => {
            void mutate()
            setShowForm(false)
          }}
          onCancel={() => setShowForm(false)}
        />
      )}

      <div className="mb-5 flex items-center justify-between">
        <div role="tablist" className="flex gap-1 rounded-lg bg-surface-alt p-1">
          {STATUS_TABS.map((tab) => {
            const selected = tab.key === status
            return (
              <button
                key={tab.key}
                role="tab"
                aria-selected={selected}
                onClick={() => setFilters({ status: tab.key })}
                className={`flex h-8 items-center gap-1.5 rounded-md px-3 text-[13px] font-medium transition-colors ${
                  selected
                    ? "bg-surface text-foreground shadow-sm"
                    : "text-muted-strong hover:text-foreground"
                }`}
              >
                {tab.label}
                <span className="text-[11.5px] text-muted">
                  {students ? counts[tab.key] : "—"}
                </span>
              </button>
            )
          })}
        </div>

        <button
          onClick={() => setFilters({ withoutTopic: !withoutTopic })}
          aria-pressed={withoutTopic}
          className={`flex h-8 items-center gap-1.5 rounded-full border px-3 text-[12.5px] font-medium transition-colors ${
            withoutTopic
              ? "border-major-border bg-major-bg text-major-text"
              : "border-line text-muted-strong hover:text-foreground"
          }`}
        >
          Bez ustalonego tematu
          {withoutTopic && <IconX size={13} stroke={2} />}
        </button>
      </div>

      {error && (
        <p className="text-[13px] text-critical-text">Nie udało się pobrać listy.</p>
      )}

      {students?.length === 0 && <DemoStudentsOffer onLoaded={() => void mutate()} />}

      {filtered && filtered.length === 0 && students?.length !== 0 && (
        <p className="text-[13.5px] text-muted">
          {narrowed ? "Brak wyników." : "Brak studentów w tej grupie."}
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
                <th className="py-2.5 font-semibold">Ostatnia aktywność</th>
                <th className="w-12 py-2.5 pr-4">
                  <span className="sr-only">Usuń</span>
                </th>
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
                    <StatusSelect student={s} onChange={replaceStudent} />
                  </td>
                  <td className="py-3.5 text-muted">{timeAgo(s.updated_at)}</td>
                  <td className="py-3.5 pr-4 text-right">
                    <button
                      type="button"
                      aria-label={`Usuń: ${s.full_name}`}
                      title="Usuń studenta"
                      onClick={() => setDeleting(s)}
                      className="rounded-md p-1.5 text-muted hover:bg-surface-alt hover:text-critical-text"
                    >
                      <IconTrash size={15} stroke={1.75} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {deleting && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Usuń: ${deleting.full_name}`}
          onKeyDown={(e) => {
            if (e.key === "Escape") setDeleting(null)
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setDeleting(null)
          }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
        >
          <div className="w-full max-w-lg rounded-xl bg-surface shadow-xl">
            <DeleteStudentConfirm
              student={deleting}
              onDeleted={() => setDeleting(null)}
              onCancel={() => setDeleting(null)}
            />
          </div>
        </div>
      )}
    </main>
  )
}
