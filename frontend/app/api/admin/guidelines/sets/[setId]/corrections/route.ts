import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ setId: string }> }

/** Open a correction: the next version, with the rubric and regulation copied. */
export async function POST(_request: Request, { params }: Params): Promise<Response> {
  const { setId } = await params
  return proxy(`/guidelines/admin/sets/${setId}/corrections`, { method: "POST" })
}
