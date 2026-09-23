import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ id: string; draftId: string }> }

/** Mark a version as final. */
export async function POST(_request: Request, { params }: Params): Promise<Response> {
  const { id, draftId } = await params
  return proxy(`/students/${id}/drafts/${draftId}/accept`, { method: "POST" })
}

/** Undo the acceptance. */
export async function DELETE(_request: Request, { params }: Params): Promise<Response> {
  const { id, draftId } = await params
  return proxy(`/students/${id}/drafts/${draftId}/accept`, { method: "DELETE" })
}
