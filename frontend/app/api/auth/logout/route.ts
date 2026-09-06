import { cookies } from "next/headers"
import { NextResponse } from "next/server"

import { APP_URL } from "@/lib/appProxy"

export async function POST(): Promise<Response> {
  const cookieStore = await cookies()
  const refreshToken = cookieStore.get("refresh_token")?.value

  if (refreshToken) {
    await fetch(`${APP_URL}/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    }).catch(() => {})
  }

  const response = NextResponse.json({ ok: true })
  response.cookies.set("access_token", "", { maxAge: 0, path: "/" })
  response.cookies.set("refresh_token", "", { maxAge: 0, path: "/" })
  return response
}
