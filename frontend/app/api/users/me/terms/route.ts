import { proxy } from "@/lib/appProxy"

export async function GET(): Promise<Response> {
  return proxy("/users/me/terms")
}

export async function POST(request: Request): Promise<Response> {
  return proxy("/users/me/terms", { method: "POST", json: await request.json() })
}
