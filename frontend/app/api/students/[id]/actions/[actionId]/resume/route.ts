import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ id: string; actionId: string }> }

export async function POST(request: Request, { params }: Params): Promise<Response> {
  const { id, actionId } = await params
  return proxy(`/students/${id}/actions/${actionId}/resume`, {
    method: "POST",
    json: await request.json(),
  })
}
