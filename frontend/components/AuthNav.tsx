import { cookies } from "next/headers"
import { decodeToken } from "@/lib/auth"
import Sidebar from "@/components/nav/Sidebar"

export default async function AuthNav() {
  const cookieStore = await cookies()
  const token = cookieStore.get("access_token")?.value
  const payload = token ? decodeToken(token) : null

  return <Sidebar email={payload?.email ?? null} role={payload?.role ?? null} />
}
