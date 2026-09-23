import { proxy } from "@/lib/appProxy"

export async function GET(): Promise<Response> {
  return proxy("/models/admin")
}

export async function PATCH(request: Request): Promise<Response> {
  return proxy("/models/admin", { method: "PATCH", json: await request.json() })
}
