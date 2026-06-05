import AuthNav from "@/components/AuthNav"

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <AuthNav />
      {children}
    </>
  )
}
