import { proxy } from "@/lib/appProxy"

export async function POST(request: Request): Promise<Response> {
  return proxy("/guidelines/admin/sets", { method: "POST", json: await request.json() })
}
