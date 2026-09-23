import { proxy } from "@/lib/appProxy"

export async function GET(): Promise<Response> {
  return proxy("/guidelines/universities")
}
