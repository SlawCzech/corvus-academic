import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ versionId: string }> }

export async function POST(_request: Request, { params }: Params): Promise<Response> {
  const { versionId } = await params
  return proxy(`/guidelines/admin/versions/${versionId}/publish`, { method: "POST" })
}
