import { proxy } from "@/lib/appProxy"

export async function GET(request: Request): Promise<Response> {
  const status = new URL(request.url).searchParams.get("status")
  return proxy(`/students${status ? `?status=${status}` : ""}`)
}

export async function POST(request: Request): Promise<Response> {
  return proxy("/students", { method: "POST", json: await request.json() })
}
