import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ id: string; draftId: string }> }

/** Delete a version's text and file now; `app` keeps its row in the history. */
export async function DELETE(_request: Request, { params }: Params): Promise<Response> {
  const { id, draftId } = await params
  return proxy(`/students/${id}/drafts/${draftId}`, { method: "DELETE" })
}
