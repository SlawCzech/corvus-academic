import { proxyFile } from "@/lib/appProxy"

type Params = { params: Promise<{ id: string; draftId: string }> }

/** The original PDF/DOCX of one version, as a download. */
export async function GET(_request: Request, { params }: Params): Promise<Response> {
  const { id, draftId } = await params
  return proxyFile(`/students/${id}/drafts/${draftId}/file`)
}
