import { cookies } from "next/headers"
import { NextResponse } from "next/server"

import { APP_URL } from "@/lib/appProxy"

/** An admin gives a user a temporary password; `app` returns it once. */
export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<Response> {
  const token = (await cookies()).get("access_token")?.value
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }
  const { id } = await params
  const res = await fetch(`${APP_URL}/users/${id}/password-reset`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  })
  const body = (await res.json().catch(() => ({}))) as {
    temporary_password?: string
    detail?: unknown
  }
  if (!res.ok) {
    return NextResponse.json(
      { detail: typeof body.detail === "string" ? body.detail : undefined },
      { status: res.status },
    )
  }
  return NextResponse.json(
    { temporary_password: body.temporary_password },
    { headers: { "Cache-Control": "no-store" } },
  )
}
