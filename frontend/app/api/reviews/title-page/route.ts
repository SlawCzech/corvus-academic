import { proxy } from "@/lib/appProxy"

/** Suggest the form's fields from a thesis — forwarded as multipart, stored nowhere. */
export async function POST(request: Request): Promise<Response> {
  return proxy("/reviews/title-page", { method: "POST", body: await request.formData() })
}
