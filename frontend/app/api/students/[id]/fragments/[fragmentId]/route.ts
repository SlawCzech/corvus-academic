import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ id: string; fragmentId: string }> }

/** Take back a mistaken upload, with its file and its AI runs. */
export async function DELETE(_request: Request, { params }: Params): Promise<Response> {
  const { id, fragmentId } = await params
  return proxy(`/students/${id}/fragments/${fragmentId}`, { method: "DELETE" })
}
