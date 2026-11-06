import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ versionId: string }> }

/** Have the model draft the rubric from the attached regulation (ADR 0025). */
export async function POST(request: Request, { params }: Params): Promise<Response> {
  const { versionId } = await params
  return proxy(`/guidelines/admin/versions/${versionId}/draft-rubric`, {
    method: "POST",
    json: await request.json(),
  })
}
