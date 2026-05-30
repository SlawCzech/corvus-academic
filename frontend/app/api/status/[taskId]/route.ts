import { NextResponse } from "next/server"

const GATEWAY_URL = process.env.GATEWAY_URL ?? "http://localhost:8000"
const GATEWAY_TOKEN = process.env.GATEWAY_SERVICE_TOKEN ?? ""

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ taskId: string }> },
): Promise<Response> {
  const { taskId } = await params
  const res = await fetch(`${GATEWAY_URL}/analysis/${taskId}`, {
    headers: { Authorization: `Bearer ${GATEWAY_TOKEN}` },
  })
  if (!res.ok) {
    return NextResponse.json(
      { error: "Status check failed" },
      { status: res.status },
    )
  }
  return Response.json(await res.json())
}
