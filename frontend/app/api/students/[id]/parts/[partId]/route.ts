import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ id: string; partId: string }> }

export async function PATCH(request: Request, { params }: Params): Promise<Response> {
  const { id, partId } = await params
  return proxy(`/students/${id}/parts/${partId}`, {
    method: "PATCH",
    json: await request.json(),
  })
}

export async function DELETE(_request: Request, { params }: Params): Promise<Response> {
  const { id, partId } = await params
  return proxy(`/students/${id}/parts/${partId}`, { method: "DELETE" })
}
