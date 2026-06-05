import { cookies } from "next/headers"
import { NextResponse } from "next/server"

const GATEWAY_URL = process.env.GATEWAY_URL ?? "http://localhost:8000"

export async function PATCH(request: Request): Promise<Response> {
  const token = (await cookies()).get("access_token")?.value
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }
  const body = (await request.json()) as {
    current_password: string
    new_password: string
  }
  const res = await fetch(`${GATEWAY_URL}/users/me/password`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    return NextResponse.json({ error: "Failed to change password" }, { status: res.status })
  }
  return NextResponse.json({ ok: true })
}
