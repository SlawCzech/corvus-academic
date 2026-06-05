import { cookies } from "next/headers"
import { decodeToken } from "@/lib/auth"
import Nav from "@/components/landing/Nav"

export default async function AuthNav() {
  const cookieStore = await cookies()
  const token = cookieStore.get("access_token")?.value
  const payload = token ? decodeToken(token) : null

  return <Nav role={payload?.role} isLoggedIn={true} />
}
