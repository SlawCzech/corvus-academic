import { cookies } from "next/headers"
import { NextResponse } from "next/server"

const GATEWAY_URL = process.env.GATEWAY_URL ?? "http://localhost:8000"

export async function GET(): Promise<Response> {
  const token = (await cookies()).get("access_token")?.value
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }
  const res = await fetch(`${GATEWAY_URL}/admin/login-events`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    return NextResponse.json({ error: "Failed to fetch login events" }, { status: res.status })
  }
  return Response.json(await res.json())
}
