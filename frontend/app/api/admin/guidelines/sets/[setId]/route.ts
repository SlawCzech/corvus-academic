import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ setId: string }> }

/** Delete a set with every version, to start again from the regulation. */
export async function DELETE(_request: Request, { params }: Params): Promise<Response> {
  const { setId } = await params
  return proxy(`/guidelines/admin/sets/${setId}`, { method: "DELETE" })
}
