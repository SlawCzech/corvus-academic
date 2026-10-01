import { proxy } from "@/lib/appProxy"

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ provider: string }> },
): Promise<Response> {
  const { provider } = await params
  return proxy(`/settings/api-key/${encodeURIComponent(provider)}`, { method: "DELETE" })
}
