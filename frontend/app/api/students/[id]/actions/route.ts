import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ id: string }> }

export async function GET(request: Request, { params }: Params): Promise<Response> {
  const { id } = await params
  const type = new URL(request.url).searchParams.get("type")
  return proxy(`/students/${id}/actions${type ? `?type=${type}` : ""}`)
}

export async function POST(request: Request, { params }: Params): Promise<Response> {
  const { id } = await params
  return proxy(`/students/${id}/actions`, {
    method: "POST",
    json: await request.json(),
  })
}
