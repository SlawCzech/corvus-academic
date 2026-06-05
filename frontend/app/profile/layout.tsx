import AuthNav from "@/components/AuthNav"

export default function ProfileLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <AuthNav />
      {children}
    </>
  )
}
