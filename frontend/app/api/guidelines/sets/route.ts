import { proxy } from "@/lib/appProxy"

/** The catalog, optionally narrowed to one thesis type (`?thesis_type=`). */
export async function GET(request: Request): Promise<Response> {
  const thesisType = new URL(request.url).searchParams.get("thesis_type")
  return proxy(
    `/guidelines/sets${thesisType ? `?thesis_type=${encodeURIComponent(thesisType)}` : ""}`,
  )
}
