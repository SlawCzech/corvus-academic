import { proxy } from "@/lib/appProxy"

type Params = { params: Promise<{ id: string; actionId: string }> }

/** Poll one action — `app` refreshes it from the agent while it is running. */
export async function GET(_request: Request, { params }: Params): Promise<Response> {
  const { id, actionId } = await params
  return proxy(`/students/${id}/actions/${actionId}`)
}

/** Delete the action from the history, here and in the agent. */
export async function DELETE(_request: Request, { params }: Params): Promise<Response> {
  const { id, actionId } = await params
  return proxy(`/students/${id}/actions/${actionId}`, { method: "DELETE" })
}
