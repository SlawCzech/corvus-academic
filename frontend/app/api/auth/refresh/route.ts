import { cookies } from "next/headers"
import { NextResponse, type NextRequest } from "next/server"

import { APP_URL, refreshTokenIn, safeRedirectPath } from "@/lib/appProxy"
import { ACCESS_COOKIE_MAX_AGE, REFRESH_COOKIE_MAX_AGE } from "@/lib/auth"

/**
 * A relative `Location`, on purpose: behind Caddy `request.url` carries the
 * container's address, and an absolute redirect built from it leaves the site.
 */
function redirectTo(path: string): NextResponse {
  return new NextResponse(null, { status: 307, headers: { Location: path } })
}

async function renew(refreshToken: string): Promise<Response | null> {
  try {
    return await fetch(`${APP_URL}/auth/refresh`, {
      method: "POST",
      headers: { Cookie: `refresh_token=${refreshToken}` },
    })
  } catch {
    return null
  }
}

export async function POST(request: NextRequest): Promise<Response> {
  const cookieStore = await cookies()
  const refreshToken = cookieStore.get("refresh_token")?.value

  // The middleware sends a browser here mid-navigation and wants it sent
  // onwards; the API client calls the same route from a fetch and wants an
  // answer, not a redirect to a page it would have to parse as HTML.
  const redirect = safeRedirectPath(request.nextUrl.searchParams.get("redirect"))

  if (!refreshToken) {
    return redirect
      ? redirectTo("/login")
      : NextResponse.json({ error: "No refresh token" }, { status: 401 })
  }

  const upstream = await renew(refreshToken)

  if (upstream?.status === 401) {
    const response = redirect
      ? redirectTo("/login")
      : NextResponse.json({ error: "Refresh failed" }, { status: 401 })
    response.cookies.set("access_token", "", { maxAge: 0, path: "/" })
    response.cookies.set("refresh_token", "", { maxAge: 0, path: "/" })
    return response
  }

  // `app` being down says nothing about the session: a deploy must not log
  // anyone out, so the cookies stay for the next attempt.
  if (!upstream?.ok) {
    return redirect
      ? redirectTo("/login")
      : NextResponse.json({ error: "Refresh unavailable" }, { status: 503 })
  }

  const data = (await upstream.json()) as { access_token: string }
  const rotated = refreshTokenIn(upstream)

  const response = redirect ? redirectTo(redirect) : NextResponse.json({ ok: true })
  response.cookies.set("access_token", data.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: ACCESS_COOKIE_MAX_AGE,
  })
  // `app` retires the token it was just given, so this one has to be kept.
  if (rotated) {
    response.cookies.set("refresh_token", rotated, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: REFRESH_COOKIE_MAX_AGE,
    })
  }
  return response
}

export async function GET(request: NextRequest): Promise<Response> {
  return POST(request)
}
