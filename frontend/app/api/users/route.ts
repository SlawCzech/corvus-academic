import { cookies } from "next/headers"
import { NextResponse } from "next/server"

const GATEWAY_URL = process.env.GATEWAY_URL ?? "http://localhost:8000"

async function getToken(): Promise<string | null> {
  return (await cookies()).get("access_token")?.value ?? null
}

export async function GET(): Promise<Response> {
  const token = await getToken()
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }
  const res = await fetch(`${GATEWAY_URL}/users`, {
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
  const body = (await request.json()) as {
    email: string
    password: string
    role: string
  }
  const res = await fetch(`${GATEWAY_URL}/users`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    return NextResponse.json({ error: "Failed to create user" }, { status: res.status })
  }
  return NextResponse.json(await res.json(), { status: 201 })
}
