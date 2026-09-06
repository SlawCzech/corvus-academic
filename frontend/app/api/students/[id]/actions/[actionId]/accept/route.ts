import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ id: string; actionId: string }> }

export async function PATCH(request: Request, { params }: Params): Promise<Response> {
  const { id, actionId } = await params
  return proxy(`/students/${id}/actions/${actionId}/accept`, {
    method: "PATCH",
    json: await request.json(),
  })
}
