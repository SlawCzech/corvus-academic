import AuthNav from "@/components/AuthNav"

export default function AnalysisLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <AuthNav />
      {children}
    </>
  )
}
