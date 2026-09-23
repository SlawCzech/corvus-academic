import { proxy } from "@/lib/appProxy"

export async function PUT(request: Request): Promise<Response> {
  return proxy("/models/admin/default", { method: "PUT", json: await request.json() })
}
