import { NextResponse } from "next/server"

import { APP_URL } from "@/lib/appProxy"

/**
 * Public — submitted from the login screen before anyone is signed in, so
 * this can't go through `proxy()` (which requires a session cookie).
 */
export async function POST(request: Request): Promise<Response> {
  const body = (await request.json()) as { email: string }
  const upstream = await fetch(`${APP_URL}/access-requests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  })

  const text = await upstream.text()
  if (!text) return new NextResponse(null, { status: upstream.status })
  return new NextResponse(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  })
}
