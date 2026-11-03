import { describe, it, expect } from "vitest"
import { NextRequest } from "next/server"
import { config, proxy } from "./proxy"

function fakeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.fakesig`
}

function makeRequest(path: string, token?: string): NextRequest {
  const headers: Record<string, string> = {}
  if (token) headers["cookie"] = `access_token=${token}`
  return new NextRequest(`http://localhost${path}`, { headers })
}

describe("proxy", () => {
  it("redirects /admin to /login when no token", () => {
    const res = proxy(makeRequest("/admin"))
    expect(res.status).toBe(307)
    expect(res.headers.get("location")).toContain("/login")
  })

  it("redirects /analysis to /login when no token", () => {
    const res = proxy(makeRequest("/analysis"))
    expect(res.status).toBe(307)
    expect(res.headers.get("location")).toContain("/login")
  })

  it("redirects /admin to /login when role is promotor", () => {
    // Role values are the identity service's own `Role` StrEnum — lowercase
    // ("admin"/"promotor"), not the uppercase strings this test used to
    // assert: those never matched a real token, so this gate silently
    // blocked every real admin from every /admin/* page.
    const token = fakeJwt({ sub: "u1", role: "promotor", exp: 9999999999 })
    const res = proxy(makeRequest("/admin", token))
    expect(res.status).toBe(307)
    expect(res.headers.get("location")).toContain("/login")
  })

  it("allows /admin through when role is admin", () => {
    const token = fakeJwt({ sub: "u1", role: "admin", exp: 9999999999 })
    const res = proxy(makeRequest("/admin", token))
    expect(res.headers.get("location")).toBeNull()
  })

  it("allows /analysis through with any valid token", () => {
    const token = fakeJwt({ sub: "u1", role: "promotor", exp: 9999999999 })
    const res = proxy(makeRequest("/analysis", token))
    expect(res.headers.get("location")).toBeNull()
  })

  it("sends an admin away from the promoter's screens", () => {
    const token = fakeJwt({ sub: "u1", role: "admin", exp: 9999999999 })
    for (const path of ["/dashboard", "/students", "/students/abc"]) {
      const res = proxy(makeRequest(path, token))
      expect(res.headers.get("location")).toBe("http://localhost/admin/users")
    }
  })

  it("sends an admin to the catalog they manage, but lets a version page through", () => {
    const token = fakeJwt({ sub: "u1", role: "admin", exp: 9999999999 })
    expect(proxy(makeRequest("/guidelines", token)).headers.get("location")).toBe(
      "http://localhost/admin/guidelines",
    )
    expect(proxy(makeRequest("/guidelines/v1", token)).headers.get("location")).toBeNull()
  })

  it("renews an expired token on a file link and comes back to the file", () => {
    const expired = fakeJwt({ sub: "u1", role: "promotor", exp: 1 })
    const path = "/api/students/s1/drafts/d1/file"
    const res = proxy(
      new NextRequest(`http://localhost${path}`, {
        headers: { cookie: `access_token=${expired}; refresh_token=ref-1` },
      }),
    )
    const location = new URL(res.headers.get("location")!)
    expect(location.pathname).toBe("/api/auth/refresh")
    expect(location.searchParams.get("redirect")).toBe(path)
  })

  it("covers every file link", () => {
    expect(config.matcher).toEqual(
      expect.arrayContaining([
        "/api/students/:student/drafts/:draft/file",
        "/api/students/:student/fragments/:fragment/file",
        "/api/guidelines/versions/:version/source",
      ]),
    )
  })

  it("lets a promoter into the roster", () => {
    const token = fakeJwt({ sub: "u1", role: "promotor", exp: 9999999999 })
    expect(proxy(makeRequest("/students", token)).headers.get("location")).toBeNull()
  })
})
