import { proxy } from "@/lib/appProxy"

export async function GET(): Promise<Response> {
  return proxy("/reviews")
}

/** A thesis to review once — forwarded as multipart, parsed by `app`. */
export async function POST(request: Request): Promise<Response> {
  return proxy("/reviews", { method: "POST", body: await request.formData() })
}
