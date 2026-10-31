import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ id: string }> }

/** Record one fragment — forwarded as multipart, parsed by `app`. */
export async function POST(request: Request, { params }: Params): Promise<Response> {
  const { id } = await params
  const form = await request.formData()
  return proxy(`/students/${id}/fragments`, { method: "POST", body: form })
}
