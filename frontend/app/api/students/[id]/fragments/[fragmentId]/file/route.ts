import { proxyFile } from "@/lib/appProxy"

type Params = { params: Promise<{ id: string; fragmentId: string }> }

/** The original PDF/DOCX of one fragment, as a download. */
export async function GET(_request: Request, { params }: Params): Promise<Response> {
  const { id, fragmentId } = await params
  return proxyFile(`/students/${id}/fragments/${fragmentId}/file`)
}
