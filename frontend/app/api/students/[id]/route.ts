import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ id: string }> }

export async function GET(_request: Request, { params }: Params): Promise<Response> {
  const { id } = await params
  return proxy(`/students/${id}`)
}

export async function PATCH(request: Request, { params }: Params): Promise<Response> {
  const { id } = await params
  return proxy(`/students/${id}`, { method: "PATCH", json: await request.json() })
}

/** Delete the student for good — notes, versions, files and AI results. */
export async function DELETE(_request: Request, { params }: Params): Promise<Response> {
  const { id } = await params
  return proxy(`/students/${id}`, { method: "DELETE" })
}
