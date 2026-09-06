import StudentDetail from "@/components/students/StudentDetail"

export default async function StudentPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  return <StudentDetail studentId={id} />
}
