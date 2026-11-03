import { cookies } from "next/headers"
import { NextResponse } from "next/server"

import { ACCESS_COOKIE_MAX_AGE, REFRESH_COOKIE_MAX_AGE } from "@/lib/auth"

/**
 * Base URL of the `app` service.
 *
 * One variable, not the old GATEWAY_URL/PARSER_URL pair: since the Phase 0
 * consolidation both pointed at the same service.
 */
export const APP_URL = process.env.APP_URL ?? "http://localhost:8000"

/**
 * The browser's address, for `app`'s rate limits.
 *
 * Every request reaches `app` from this server, so without it all logins in
 * the world share one limit — five a minute, then everyone is locked out.
 * In production Caddy sets `X-Forwarded-For` to the address it saw, replacing
 * whatever the browser sent; locally there is no proxy and nothing to pass.
 */
export function forwardedFor(request: Request): Record<string, string> {
  const forwarded = request.headers.get("x-forwarded-for")
  return forwarded ? { "X-Forwarded-For": forwarded } : {}
}

/**
 * The refresh token out of `app`'s `Set-Cookie`.
 *
 * It never travels in the JSON body, and a cookie that `app` scopes to its own
 * `/auth/refresh` means nothing to the browser here: the route has to lift it
 * out and set a cookie of this site.
 */
export function refreshTokenIn(upstream: Response): string | null {
  for (const header of upstream.headers.getSetCookie()) {
    const match = /^refresh_token=([^;]+)/.exec(header)
    if (match) return match[1]
  }
  return null
}

/**
 * Put a session `app` has just issued into this site's cookies.
 *
 * Login, refresh and a password change all end with a fresh pair; the
 * refresh token is absent only when `app` did not send one.
 */
export function setSession(
  response: NextResponse,
  accessToken: string,
  refreshToken: string | null,
): void {
  const options = {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
  } as const
  response.cookies.set("access_token", accessToken, {
    ...options,
    maxAge: ACCESS_COOKIE_MAX_AGE,
  })
  if (refreshToken) {
    response.cookies.set("refresh_token", refreshToken, {
      ...options,
      maxAge: REFRESH_COOKIE_MAX_AGE,
    })
  }
}

/**
 * Where to send the browser after a refresh: a path on this site, or home.
 * `new URL("//evil.example", base)` and absolute URLs leave the site, so
 * anything but a single-slash path is refused.
 */
export function safeRedirectPath(value: string | null): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
    return null
  }
  return value
}

interface ProxyInit {
  method?: string
  /** Serialised as a JSON request body. */
  json?: unknown
  /** Passed through as-is — used for multipart uploads. */
  body?: BodyInit
}

/**
 * Forward a request to `app` with the caller's access token.
 *
 * The upstream status and body are passed back untouched, so the UI can show
 * why something was refused (a 409 explains what the student's record is
 * missing) instead of a generic failure.
 */
export async function proxy(path: string, init: ProxyInit = {}): Promise<Response> {
  const token = (await cookies()).get("access_token")?.value
  if (!token) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 })
  }

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` }
  let body = init.body
  if (init.json !== undefined) {
    headers["Content-Type"] = "application/json"
    body = JSON.stringify(init.json)
  }

  const upstream = await fetch(`${APP_URL}${path}`, {
    method: init.method ?? "GET",
    headers,
    body,
    cache: "no-store",
  })

  const text = await upstream.text()
  if (!text) return new NextResponse(null, { status: upstream.status })
  return new NextResponse(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  })
}

/**
 * Forward a file download from `app` untouched.
 *
 * `proxy()` reads the body as text and labels it JSON, which would corrupt a
 * PDF or DOCX. This streams the bytes and keeps the headers that make it a
 * download: the type, the attachment disposition with the original filename,
 * and `nosniff`. An error from `app` still arrives as its JSON explanation.
 */
export async function proxyFile(path: string): Promise<Response> {
  const token = (await cookies()).get("access_token")?.value
  if (!token) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 })
  }

  const upstream = await fetch(`${APP_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  })

  const headers = new Headers()
  for (const name of ["content-type", "content-disposition", "x-content-type-options"]) {
    const value = upstream.headers.get(name)
    if (value) headers.set(name, value)
  }
  return new Response(upstream.body, { status: upstream.status, headers })
}
