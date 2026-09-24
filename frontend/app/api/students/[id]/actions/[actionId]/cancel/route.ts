import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ id: string; actionId: string }> }

export async function POST(_request: Request, { params }: Params): Promise<Response> {
  const { id, actionId } = await params
  return proxy(`/students/${id}/actions/${actionId}/cancel`, { method: "POST" })
}
