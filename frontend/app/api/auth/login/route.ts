import { NextResponse } from "next/server"

const GATEWAY_URL = process.env.GATEWAY_URL ?? "http://localhost:8000"

export async function POST(request: Request): Promise<Response> {
  const body = (await request.json()) as { email?: string; password?: string }
  const gatewayRes = await fetch(`${GATEWAY_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!gatewayRes.ok) {
    return NextResponse.json({ error: "Invalid credentials" }, { status: 401 })
  }
  const data = (await gatewayRes.json()) as { access_token: string }
  const response = NextResponse.json({ ok: true })
  response.cookies.set("token", data.access_token, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24,
  })
  return response
}
