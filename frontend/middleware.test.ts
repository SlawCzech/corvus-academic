import { describe, it, expect } from "vitest"
import { NextRequest } from "next/server"
import { middleware } from "./middleware"

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

describe("middleware", () => {
  it("redirects /admin to /login when no token", () => {
    const res = middleware(makeRequest("/admin"))
    expect(res.status).toBe(307)
    expect(res.headers.get("location")).toContain("/login")
  })

  it("redirects /analysis to /login when no token", () => {
    const res = middleware(makeRequest("/analysis"))
    expect(res.status).toBe(307)
    expect(res.headers.get("location")).toContain("/login")
  })

  it("redirects /admin to /login when role is promotor", () => {
    // Role values are the identity service's own `Role` StrEnum — lowercase
    // ("admin"/"promotor"), not the uppercase strings this test used to
    // assert: those never matched a real token, so this gate silently
    // blocked every real admin from every /admin/* page.
    const token = fakeJwt({ sub: "u1", role: "promotor", exp: 9999999999 })
    const res = middleware(makeRequest("/admin", token))
    expect(res.status).toBe(307)
    expect(res.headers.get("location")).toContain("/login")
  })

  it("allows /admin through when role is admin", () => {
    const token = fakeJwt({ sub: "u1", role: "admin", exp: 9999999999 })
    const res = middleware(makeRequest("/admin", token))
    expect(res.headers.get("location")).toBeNull()
  })

  it("allows /analysis through with any valid token", () => {
    const token = fakeJwt({ sub: "u1", role: "promotor", exp: 9999999999 })
    const res = middleware(makeRequest("/analysis", token))
    expect(res.headers.get("location")).toBeNull()
  })
})
