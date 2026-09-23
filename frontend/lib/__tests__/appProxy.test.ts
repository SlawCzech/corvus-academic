import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("next/headers", () => ({
  cookies: () => Promise.resolve({ get: () => ({ value: "token-123" }) }),
}))

import { proxyFile } from "@/lib/appProxy"

/**
 * `proxy()` reads every body as text and labels it JSON — fine for the API,
 * fatal for a DOCX. Downloads go through `proxyFile`, which must pass the
 * bytes and the download headers through untouched.
 */
describe("proxyFile", () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock)
    fetchMock.mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("passes the bytes and the attachment headers through", async () => {
    const bytes = new Uint8Array([0x50, 0x4b, 0x03, 0x04, 0xff, 0x00])
    fetchMock.mockResolvedValueOnce(
      new Response(bytes, {
        status: 200,
        headers: {
          "content-type": "application/pdf",
          "content-disposition": "attachment; filename*=UTF-8''praca.pdf",
          "x-content-type-options": "nosniff",
          "x-internal": "not forwarded",
        },
      }),
    )

    const res = await proxyFile("/students/s1/drafts/d1/file")

    expect(new Uint8Array(await res.arrayBuffer())).toEqual(bytes)
    expect(res.headers.get("content-type")).toBe("application/pdf")
    expect(res.headers.get("content-disposition")).toContain("attachment")
    expect(res.headers.get("x-content-type-options")).toBe("nosniff")
    expect(res.headers.get("x-internal")).toBeNull()
    expect(fetchMock.mock.calls[0][1].headers).toEqual({ Authorization: "Bearer token-123" })
  })

  it("keeps the upstream status of a refusal", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Not found" }), { status: 404 }),
    )

    const res = await proxyFile("/students/s1/drafts/d9/file")

    expect(res.status).toBe(404)
  })
})
