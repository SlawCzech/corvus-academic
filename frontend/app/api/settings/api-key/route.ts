import { proxy } from "@/lib/appProxy"

export async function PATCH(request: Request): Promise<Response> {
  return proxy("/settings/api-key", {
    method: "PATCH",
    json: await request.json(),
  })
}
