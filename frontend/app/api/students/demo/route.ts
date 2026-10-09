import { proxy } from "@/lib/appProxy"

export async function POST(): Promise<Response> {
  return proxy("/students/demo", { method: "POST" })
}
