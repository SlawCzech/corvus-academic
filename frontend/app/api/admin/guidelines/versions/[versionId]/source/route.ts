import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ versionId: string }> }

/** Attach the original regulation to a draft — forwarded as multipart. */
export async function PUT(request: Request, { params }: Params): Promise<Response> {
  const { versionId } = await params
  const form = await request.formData()
  return proxy(`/guidelines/admin/versions/${versionId}/source`, {
    method: "PUT",
    body: form,
  })
}
