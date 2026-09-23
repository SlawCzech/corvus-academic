import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ setId: string }> }

/** Open the next version of a set as a draft. */
export async function POST(request: Request, { params }: Params): Promise<Response> {
  const { setId } = await params
  return proxy(`/guidelines/admin/sets/${setId}/versions`, {
    method: "POST",
    json: await request.json(),
  })
}
