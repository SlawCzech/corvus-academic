import { readFile } from "node:fs/promises"
import path from "node:path"

// Not in `public/`: everything there is open to anyone, and the guide is for
// people with an account. `proxy.ts` sends a visitor without a session to the
// login page before this runs.
const GUIDE_FILE = path.join(process.cwd(), "content", "guide", "przewodnik-promotora.pdf")

export async function GET(): Promise<Response> {
  const pdf = await readFile(GUIDE_FILE)
  return new Response(new Uint8Array(pdf), {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": 'inline; filename="corvus-przewodnik-promotora.pdf"',
      "Cache-Control": "private, max-age=3600",
    },
  })
}
