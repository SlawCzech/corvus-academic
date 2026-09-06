import { proxy } from "@/lib/appProxy"

export async function PATCH(request: Request): Promise<Response> {
  return proxy("/settings/api-key", {
    method: "PATCH",
    json: await request.json(),
  })
}

export async function DELETE(): Promise<Response> {
  return proxy("/settings/api-key", { method: "DELETE" })
}
