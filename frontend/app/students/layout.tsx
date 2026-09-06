import AuthNav from "@/components/AuthNav"

export default function StudentsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <>
      <AuthNav />
      {children}
    </>
  )
}
