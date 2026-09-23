import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ setId: string }> }

export async function GET(_request: Request, { params }: Params): Promise<Response> {
  const { setId } = await params
  return proxy(`/guidelines/sets/${setId}`)
}
