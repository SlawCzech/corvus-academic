import AuthNav from "@/components/AuthNav"

export default function GuidelinesLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <AuthNav />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}
