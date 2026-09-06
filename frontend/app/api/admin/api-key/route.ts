import { NextResponse } from "next/server"
import { cookies } from "next/headers"

import { APP_URL } from "@/lib/appProxy"

export async function PATCH(request: Request): Promise<Response> {
  const cookieStore = await cookies()
  const token = cookieStore.get("access_token")?.value
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }
  const body = (await request.json()) as { api_key: string; provider: string }
  const gatewayRes = await fetch(`${APP_URL}/settings/api-key`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  })
  if (!gatewayRes.ok) {
    return NextResponse.json(
      { error: "Failed to save API key" },
      { status: gatewayRes.status },
    )
  }
  return NextResponse.json({ ok: true })
}
