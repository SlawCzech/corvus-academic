"use client"

import { useState } from "react"
import StudentForm from "@/components/students/StudentForm"
import type { Student } from "@/lib/api.types"

const THESIS_TYPE_LABELS: Record<Student["thesis_type"], string> = {
  bachelor: "Licencjacka",
  master_article: "Magisterska (artykuł)",
}

interface Props {
  student: Student
  onChange: (student: Student) => void
}

/** The student's own details, read-only until the promoter chooses to edit. */
export default function StudentDetailsCard({ student, onChange }: Props) {
  const [editing, setEditing] = useState(false)

  if (editing) {
    return (
      <div className="col-span-2">
        <StudentForm
          student={student}
          onSaved={(next) => {
            onChange(next)
            setEditing(false)
          }}
          onCancel={() => setEditing(false)}
        />
      </div>
    )
  }

  const rows: [string, string][] = [
    ["Imię i nazwisko", student.full_name],
    ["Kierunek", student.field_of_study],
    ["Typ pracy", THESIS_TYPE_LABELS[student.thesis_type]],
    ["Obszar badawczy", student.research_area ?? "—"],
    ["Cel i hipotezy", student.research_aim ?? "—"],
  ]

  return (
    <div data-testid="student-details" className="rounded-xl border border-line bg-surface p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[11.5px] font-semibold uppercase tracking-wide text-muted">
          Dane studenta
        </h3>
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="text-[12.5px] text-accent hover:underline"
        >
          Edytuj
        </button>
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[13.5px]">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-muted">{label}</dt>
            <dd className="whitespace-pre-line text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
