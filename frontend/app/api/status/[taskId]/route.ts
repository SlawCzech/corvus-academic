import { cookies } from "next/headers"
import { NextResponse } from "next/server"

const GATEWAY_URL = process.env.GATEWAY_URL ?? "http://localhost:8000"

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ taskId: string }> },
): Promise<Response> {
  const token = (await cookies()).get("token")?.value ?? ""
  const { taskId } = await params
  const res = await fetch(`${GATEWAY_URL}/analysis/${taskId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    return NextResponse.json(
      { error: "Status check failed" },
      { status: res.status },
    )
  }
  return Response.json(await res.json())
}
