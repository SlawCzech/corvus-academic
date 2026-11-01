import { cookies } from "next/headers"
import { NextResponse } from "next/server"

import { APP_URL } from "@/lib/appProxy"

export async function PATCH(request: Request): Promise<Response> {
  const token = (await cookies()).get("access_token")?.value
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }
  const body = (await request.json()) as {
    current_password: string
    new_password: string
  }
  const res = await fetch(`${APP_URL}/users/me/password`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    // Only a sentence for the form: a validation error's `detail` is a list.
    const { detail } = (await res.json().catch(() => ({}))) as { detail?: unknown }
    return NextResponse.json(
      { detail: typeof detail === "string" ? detail : undefined },
      { status: res.status },
    )
  }
  return NextResponse.json({ ok: true })
}
