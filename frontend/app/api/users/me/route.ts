import { cookies } from "next/headers"
import { NextResponse } from "next/server"

import { APP_URL } from "@/lib/appProxy"

export async function GET(): Promise<Response> {
  const token = (await cookies()).get("access_token")?.value
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }
  const res = await fetch(`${APP_URL}/users/me`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    return NextResponse.json({ error: "Failed to fetch profile" }, { status: res.status })
  }
  return Response.json(await res.json())
}
