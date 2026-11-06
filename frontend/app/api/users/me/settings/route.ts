import { proxy } from "@/lib/appProxy"

/** The caller's own settings: the university whose guidelines come first. */
export async function GET(): Promise<Response> {
  return proxy("/users/me/settings")
}

export async function PATCH(request: Request): Promise<Response> {
  return proxy("/users/me/settings", { method: "PATCH", json: await request.json() })
}
