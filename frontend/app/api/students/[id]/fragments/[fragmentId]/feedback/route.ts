import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ id: string; fragmentId: string }> }

export async function PUT(request: Request, { params }: Params): Promise<Response> {
  const { id, fragmentId } = await params
  return proxy(`/students/${id}/fragments/${fragmentId}/feedback`, {
    method: "PUT",
    json: await request.json(),
  })
}
