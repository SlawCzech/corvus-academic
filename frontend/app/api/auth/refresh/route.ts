import { cookies } from "next/headers"
import { NextResponse, type NextRequest } from "next/server"

import { APP_URL } from "@/lib/appProxy"

export async function POST(request: NextRequest): Promise<Response> {
  const cookieStore = await cookies()
  const refreshToken = cookieStore.get("refresh_token")?.value

  if (!refreshToken) {
    return NextResponse.json({ error: "No refresh token" }, { status: 401 })
  }

  const gatewayRes = await fetch(`${APP_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })

  if (!gatewayRes.ok) {
    const response = NextResponse.json({ error: "Refresh failed" }, { status: 401 })
    response.cookies.set("access_token", "", { maxAge: 0, path: "/" })
    response.cookies.set("refresh_token", "", { maxAge: 0, path: "/" })
    return response
  }

  const data = (await gatewayRes.json()) as { access_token: string }
  const redirect = request.nextUrl.searchParams.get("redirect") ?? "/students"
  const response = NextResponse.redirect(new URL(redirect, request.url))
  response.cookies.set("access_token", data.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 15,
  })
  return response
}

export async function GET(request: NextRequest): Promise<Response> {
  return POST(request)
}
