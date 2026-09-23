"use client"

import Link from "next/link"
import {
  IconArrowLeft,
  IconEye,
  IconSparkles,
  IconFiles,
  IconMessage2,
  IconHistory,
} from "@tabler/icons-react"
import {
  STUDENT_STATUS_LABELS as STATUS_LABELS,
  STUDENT_STATUS_STYLES as STATUS_STYLES,
} from "@/components/students/format"
import type { Student } from "@/lib/api.types"

export type Section = "overview" | "actions" | "drafts" | "notes" | "history"

const SECTIONS: { key: Section; label: string; icon: typeof IconEye }[] = [
  { key: "overview", label: "Przegląd", icon: IconEye },
  { key: "actions", label: "Akcje AI", icon: IconSparkles },
  { key: "drafts", label: "Wersje pracy", icon: IconFiles },
  { key: "notes", label: "Notatki ze spotkań", icon: IconMessage2 },
  { key: "history", label: "Historia", icon: IconHistory },
]

function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("")
}

interface StudentSubNavProps {
  student: Student
  section: Section
  onSectionChange: (section: Section) => void
}

export default function StudentSubNav({
  student,
  section,
  onSectionChange,
}: StudentSubNavProps) {
  return (
    <aside className="w-64 shrink-0 border-r border-line bg-surface-alt px-4 py-6">
      <Link
        href="/students"
        className="mb-5 flex items-center gap-1.5 text-[12.5px] text-muted hover:text-accent"
      >
        <IconArrowLeft size={13} stroke={2} />
        Studenci
      </Link>

      <div className="mb-5 px-2">
        <div className="mb-2.5 flex h-10 w-10 items-center justify-center rounded-full bg-accent-soft text-[15px] font-semibold text-accent-hover">
          {initials(student.full_name)}
        </div>
        <span className="block text-[15px] font-semibold text-foreground">
          {student.full_name}
        </span>
        <span className="mt-0.5 block text-[12px] text-muted">
          {student.field_of_study}
          {student.index_number ? ` · nr ${student.index_number}` : ""}
        </span>
        <span
          className={`mt-2.5 inline-flex rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
            STATUS_STYLES[student.status] ?? "bg-surface-alt text-muted-strong"
          }`}
        >
          {STATUS_LABELS[student.status] ?? student.status}
        </span>
      </div>

      <nav className="flex flex-col gap-0.5">
        {SECTIONS.map(({ key, label, icon: Icon }) => {
          const active = section === key
          return (
            <button
              key={key}
              type="button"
              onClick={() => onSectionChange(key)}
              className={`flex h-10 items-center gap-2.5 rounded-lg border-l-[3px] px-3 text-left text-[13.5px] transition-colors ${
                active
                  ? "border-accent bg-accent-soft font-semibold text-accent-hover"
                  : "border-transparent font-medium text-muted-strong hover:bg-black/[0.03]"
              }`}
            >
              <Icon size={16} stroke={1.75} />
              {label}
            </button>
          )
        })}
      </nav>
    </aside>
  )
}
