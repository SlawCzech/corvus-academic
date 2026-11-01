import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { NextRequest } from "next/server"

const jar = new Map<string, string>()

vi.mock("next/headers", () => ({
  cookies: () =>
    Promise.resolve({
      get: (name: string) => (jar.has(name) ? { value: jar.get(name) } : undefined),
    }),
}))

import { POST as login } from "@/app/api/auth/login/route"
import { GET, POST } from "@/app/api/auth/refresh/route"

const APP_COOKIE = "refresh_token=ref-new; HttpOnly; Max-Age=2592000; Path=/auth/refresh; SameSite=strict"

function fromApp(body: unknown, status = 200, setCookie?: string): Response {
  const headers = new Headers({ "Content-Type": "application/json" })
  if (setCookie) headers.append("Set-Cookie", setCookie)
  return new Response(JSON.stringify(body), { status, headers })
}

function setCookies(res: Response): string {
  return res.headers.getSetCookie().join("\n")
}

/**
 * `app` hands the refresh token over in `Set-Cookie` and reads it back from
 * `Cookie`. For a while these routes looked for it in JSON both ways, so no
 * session was ever renewed and everyone logged in again after twelve hours.
 */
describe("session routes", () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    jar.clear()
    vi.stubGlobal("fetch", fetchMock)
    fetchMock.mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("login keeps the refresh token that app sets as a cookie", async () => {
    fetchMock.mockResolvedValueOnce(fromApp({ access_token: "a.e30.c" }, 200, APP_COOKIE))

    const res = await login(
      new Request("http://test/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: "a@b.pl", password: "x" }),
      }),
    )

    const cookies = setCookies(res)
    expect(cookies).toMatch(/refresh_token=ref-new;/)
    expect(cookies).toMatch(/refresh_token=[^\n]*Path=\//)
  })

  it("refresh sends the token as a cookie and keeps the rotated one", async () => {
    jar.set("refresh_token", "ref-old")
    fetchMock.mockResolvedValueOnce(fromApp({ access_token: "acc-new" }, 200, APP_COOKIE))

    const res = await POST(new NextRequest("http://test/api/auth/refresh", { method: "POST" }))

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toMatch(/\/auth\/refresh$/)
    expect(init.headers).toEqual({ Cookie: "refresh_token=ref-old" })
    expect(res.status).toBe(200)
    const cookies = setCookies(res)
    expect(cookies).toMatch(/access_token=acc-new;/)
    expect(cookies).toMatch(/refresh_token=ref-new;/)
  })

  it("sends a navigating browser onwards with a relative redirect", async () => {
    jar.set("refresh_token", "ref-old")
    fetchMock.mockResolvedValueOnce(fromApp({ access_token: "acc-new" }, 200, APP_COOKIE))

    // What Caddy's upstream looks like from inside the container.
    const res = await GET(
      new NextRequest("http://172.18.0.5:3000/api/auth/refresh?redirect=/students/1"),
    )

    expect(res.status).toBe(307)
    expect(res.headers.get("location")).toBe("/students/1")
    expect(setCookies(res)).toMatch(/refresh_token=ref-new;/)
  })

  it("clears the session when app refuses the token", async () => {
    jar.set("refresh_token", "ref-old")
    fetchMock.mockResolvedValueOnce(fromApp({ detail: "revoked" }, 401))

    const res = await POST(new NextRequest("http://test/api/auth/refresh", { method: "POST" }))

    expect(res.status).toBe(401)
    const cookies = setCookies(res)
    expect(cookies).toMatch(/access_token=;/)
    expect(cookies).toMatch(/refresh_token=;/)
  })

  it("sends a navigating browser to the login page, not to raw JSON", async () => {
    jar.set("refresh_token", "ref-old")
    fetchMock.mockResolvedValueOnce(fromApp({ detail: "revoked" }, 401))

    const res = await GET(new NextRequest("http://test/api/auth/refresh?redirect=/dashboard"))

    expect(res.status).toBe(307)
    expect(res.headers.get("location")).toBe("/login")
  })

  it.each([
    ["answers 502", () => fetchMock.mockResolvedValueOnce(fromApp({}, 502))],
    ["cannot be reached", () => fetchMock.mockRejectedValueOnce(new Error("down"))],
  ])("keeps the cookies when app %s", async (_name, arrange) => {
    jar.set("refresh_token", "ref-old")
    arrange()

    const res = await POST(new NextRequest("http://test/api/auth/refresh", { method: "POST" }))

    expect(res.status).toBe(503)
    expect(setCookies(res)).toBe("")
  })

  it("does not call app without a refresh token", async () => {
    const res = await POST(new NextRequest("http://test/api/auth/refresh", { method: "POST" }))

    expect(res.status).toBe(401)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
