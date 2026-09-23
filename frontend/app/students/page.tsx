import { Suspense } from "react"
import StudentList from "@/components/students/StudentList"

export default function StudentsPage() {
  // StudentList reads its filters from the URL (useSearchParams).
  return (
    <Suspense>
      <StudentList />
    </Suspense>
  )
}
