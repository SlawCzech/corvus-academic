"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import DeleteStudentConfirm from "@/components/students/DeleteStudentConfirm"
import type { Student } from "@/lib/api.types"

/** The overview's way in to deleting the student: a quiet link, then the confirmation. */
export default function DeleteStudentPanel({ student }: { student: Student }) {
  const router = useRouter()
  const [open, setOpen] = useState(false)

  if (!open) {
    return (
      <div className="col-span-2 text-right">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="text-[12.5px] text-muted hover:text-critical-text"
        >
          Usuń studenta
        </button>
      </div>
    )
  }

  return (
    <div className="col-span-2">
      <DeleteStudentConfirm
        student={student}
        onDeleted={() => router.push("/students")}
        onCancel={() => setOpen(false)}
      />
    </div>
  )
}
