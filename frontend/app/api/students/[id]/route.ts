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
