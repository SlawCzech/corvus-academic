import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ id: string }> }

export async function GET(_request: Request, { params }: Params): Promise<Response> {
  const { id } = await params
  return proxy(`/students/${id}/drafts`)
}

/** Upload one thesis version — forwarded as multipart, parsed by `app`. */
export async function POST(request: Request, { params }: Params): Promise<Response> {
  const { id } = await params
  const form = await request.formData()
  return proxy(`/students/${id}/drafts`, { method: "POST", body: form })
}
