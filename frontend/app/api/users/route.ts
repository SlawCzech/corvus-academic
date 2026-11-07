import { cookies } from "next/headers"
import { NextResponse } from "next/server"

import { APP_URL } from "@/lib/appProxy"

async function getToken(): Promise<string | null> {
  return (await cookies()).get("access_token")?.value ?? null
}

export async function GET(): Promise<Response> {
  const token = await getToken()
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }
  const res = await fetch(`${APP_URL}/users`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    return NextResponse.json({ error: "Failed to fetch users" }, { status: res.status })
  }
  return Response.json(await res.json())
}

export async function POST(request: Request): Promise<Response> {
  const token = await getToken()
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }
  // No password: the app makes a temporary one and returns it once.
  const body = (await request.json()) as {
    email: string
    role: string
    home_university_id?: string | null
  }
  const res = await fetch(`${APP_URL}/users`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  })
  // The app's `detail` (a taken or invalid email) reaches the form as-is.
  const upstream: unknown = await res.json().catch(() => ({ detail: "Failed to create user" }))
  return NextResponse.json(upstream, { status: res.status })
}
