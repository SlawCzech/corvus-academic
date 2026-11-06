import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ versionId: string }> }

/** A version as the admin edits it, with a drafted rubric taken in once ready. */
export async function GET(_request: Request, { params }: Params): Promise<Response> {
  const { versionId } = await params
  return proxy(`/guidelines/admin/versions/${versionId}`)
}

/** Change a draft; `app` answers 409 for a published version. */
export async function PATCH(request: Request, { params }: Params): Promise<Response> {
  const { versionId } = await params
  return proxy(`/guidelines/admin/versions/${versionId}`, {
    method: "PATCH",
    json: await request.json(),
  })
}
