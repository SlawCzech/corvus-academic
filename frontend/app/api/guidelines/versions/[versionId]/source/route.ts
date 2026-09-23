import { proxyFile } from "@/lib/appProxy"

type Params = { params: Promise<{ versionId: string }> }

/** The original regulation a version was read from, as a download. */
export async function GET(_request: Request, { params }: Params): Promise<Response> {
  const { versionId } = await params
  return proxyFile(`/guidelines/versions/${versionId}/source`)
}
