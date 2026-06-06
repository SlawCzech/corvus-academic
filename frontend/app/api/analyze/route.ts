import { cookies } from "next/headers"
import { NextResponse } from "next/server"

const PARSER_URL = process.env.PARSER_URL ?? "http://localhost:8001"
const GATEWAY_URL = process.env.GATEWAY_URL ?? "http://localhost:8000"

export async function POST(request: Request): Promise<Response> {
  const token = (await cookies()).get("access_token")?.value ?? ""

  const formData = await request.formData()
  const file = formData.get("file")
  if (!(file instanceof File)) {
    return NextResponse.json({ error: "No file provided" }, { status: 400 })
  }
  const model = String(formData.get("model") ?? "qwen3:30b-a3b")
  const mode = String(formData.get("mode") ?? "full")
  const review_tone = String(formData.get("review_tone") ?? "auto")
  const thesis_type = String(formData.get("thesis_type") ?? "bachelor")
  const language = String(formData.get("language") ?? "pl")

  // Step 1: extract text via parser service
  const parserForm = new FormData()
  parserForm.append("file", file)
  const parserRes = await fetch(`${PARSER_URL}/extract`, {
    method: "POST",
    body: parserForm,
  })
  if (!parserRes.ok) {
    return NextResponse.json(
      { error: "Text extraction failed" },
      { status: 502 },
    )
  }
  const { text } = (await parserRes.json()) as { text: string }

  // Step 2: submit analysis task to gateway
  const gatewayRes = await fetch(`${GATEWAY_URL}/analysis`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      evaluation_id: crypto.randomUUID(),
      text,
      thesis_type,
      model,
      mode,
      review_tone,
      language,
    }),
  })
  if (!gatewayRes.ok) {
    return NextResponse.json(
      { error: "Analysis submission failed" },
      { status: 502 },
    )
  }
  return Response.json(await gatewayRes.json())
}
