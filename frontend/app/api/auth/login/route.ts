import { NextResponse } from "next/server"

import { APP_URL, forwardedFor, refreshTokenIn, setSession } from "@/lib/appProxy"
import { PASSWORD_PAGE, getRole, homeFor, mustChangePassword } from "@/lib/auth"

export async function POST(request: Request): Promise<Response> {
  const body = (await request.json()) as { email?: string; password?: string }
  const gatewayRes = await fetch(`${APP_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...forwardedFor(request) },
    body: JSON.stringify(body),
  })
  if (!gatewayRes.ok) {
    return NextResponse.json({ error: "Invalid credentials" }, { status: 401 })
  }
  const data = (await gatewayRes.json()) as { access_token: string }
  const refreshToken = refreshTokenIn(gatewayRes)
  // A temporary password from an admin opens nothing but its own change.
  const home = mustChangePassword(data.access_token)
    ? PASSWORD_PAGE
    : homeFor(getRole(data.access_token))
  const response = NextResponse.json({ ok: true, home })
  setSession(response, data.access_token, refreshToken)
  return response
}
