import { proxy } from "@/lib/appProxy"

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await params
  return proxy(`/access-requests/${id}`, { method: "DELETE" })
}
