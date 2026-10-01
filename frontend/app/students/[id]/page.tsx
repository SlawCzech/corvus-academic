import StudentDetail from "@/components/students/StudentDetail"
import { isSection } from "@/components/students/StudentSubNav"

export default async function StudentPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  const { id } = await params
  // `?section=actions` — how the dashboard leads straight to a waiting action.
  const { section } = await searchParams
  return (
    <StudentDetail
      studentId={id}
      initialSection={typeof section === "string" && isSection(section) ? section : undefined}
    />
  )
}
