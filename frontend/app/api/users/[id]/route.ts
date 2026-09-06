import { cookies } from "next/headers"
import { NextResponse } from "next/server"

import { APP_URL } from "@/lib/appProxy"

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<Response> {
  const token = (await cookies()).get("access_token")?.value
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }
  const { id } = await params
  const res = await fetch(`${APP_URL}/users/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    return NextResponse.json({ error: "Failed to delete user" }, { status: res.status })
  }
  return NextResponse.json({ ok: true })
}
