import { NextResponse } from "next/server"

import { APP_URL, forwardedFor } from "@/lib/appProxy"
import { ACCESS_COOKIE_MAX_AGE, REFRESH_COOKIE_MAX_AGE, getRole, homeFor } from "@/lib/auth"

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
  const data = (await gatewayRes.json()) as {
    access_token: string
    refresh_token?: string
  }
  const response = NextResponse.json({ ok: true, home: homeFor(getRole(data.access_token)) })
  response.cookies.set("access_token", data.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: ACCESS_COOKIE_MAX_AGE,
  })
  if (data.refresh_token) {
    response.cookies.set("refresh_token", data.refresh_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: REFRESH_COOKIE_MAX_AGE,
    })
  }
  return response
}
