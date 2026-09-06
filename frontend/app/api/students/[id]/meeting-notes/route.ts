import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ id: string }> }

export async function GET(_request: Request, { params }: Params): Promise<Response> {
  const { id } = await params
  return proxy(`/students/${id}/meeting-notes`)
}

export async function POST(request: Request, { params }: Params): Promise<Response> {
  const { id } = await params
  return proxy(`/students/${id}/meeting-notes`, {
    method: "POST",
    json: await request.json(),
  })
}
