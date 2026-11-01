import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ id: string }> }

export async function POST(_request: Request, { params }: Params): Promise<Response> {
  const { id } = await params
  return proxy(`/reviews/${id}/promote`, { method: "POST" })
}
