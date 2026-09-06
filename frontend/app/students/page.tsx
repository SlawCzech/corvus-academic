"use client"

import Link from "next/link"
import useSWR from "swr"
import StudentForm from "@/components/students/StudentForm"
import { fetcher } from "@/lib/api.client"
import type { Student } from "@/lib/api.types"

const STATUS_LABELS: Record<string, string> = {
  active: "Aktywny",
  graduated: "Obroniony",
  archived: "Archiwalny",
}

const THESIS_LABELS: Record<string, string> = {
  bachelor: "licencjacka",
  master_article: "magisterska",
}

export default function StudentsPage() {
  const { data: students, error, mutate } = useSWR<Student[]>(
    "/api/students",
    fetcher,
  )

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="mb-6 text-2xl font-bold text-gray-900 dark:text-gray-50">
        Studenci
      </h1>

      <StudentForm onCreated={() => void mutate()} />

      {error && (
        <p className="text-[13px] text-red-600">Nie udało się pobrać listy.</p>
      )}

      {students && students.length === 0 && (
        <p className="text-[13px] text-gray-500">
          Nie masz jeszcze żadnych studentów.
        </p>
      )}

      {students && students.length > 0 && (
        <table className="w-full text-left text-[14px]">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-800 text-[12px] uppercase tracking-wide text-gray-400">
              <th className="py-2 font-medium">Student</th>
              <th className="py-2 font-medium">Temat</th>
              <th className="py-2 font-medium">Typ</th>
              <th className="py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {students.map((s) => (
              <tr
                key={s.id}
                className="border-b border-gray-100 dark:border-gray-900"
              >
                <td className="py-3">
                  <Link
                    href={`/students/${s.id}`}
                    className="font-medium text-gray-900 dark:text-gray-100 hover:underline"
                  >
                    {s.full_name}
                  </Link>
                  <span className="block text-[12px] text-gray-400">
                    {s.field_of_study}
                  </span>
                </td>
                <td className="py-3 text-gray-600 dark:text-gray-400">
                  {s.current_topic ?? (
                    <span className="italic text-gray-400">brak tematu</span>
                  )}
                </td>
                <td className="py-3 text-gray-600 dark:text-gray-400">
                  {THESIS_LABELS[s.thesis_type] ?? s.thesis_type}
                </td>
                <td className="py-3 text-gray-600 dark:text-gray-400">
                  {STATUS_LABELS[s.status] ?? s.status}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  )
}
