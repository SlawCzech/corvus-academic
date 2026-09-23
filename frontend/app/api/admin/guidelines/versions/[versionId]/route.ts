import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ versionId: string }> }

/** Change a draft; `app` answers 409 for a published version. */
export async function PATCH(request: Request, { params }: Params): Promise<Response> {
  const { versionId } = await params
  return proxy(`/guidelines/admin/versions/${versionId}`, {
    method: "PATCH",
    json: await request.json(),
  })
}
