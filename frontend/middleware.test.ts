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
  if (token) headers["cookie"] = `token=${token}`
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

  it("redirects /admin to /login when role is PROMOTOR", () => {
    const token = fakeJwt({ sub: "u1", role: "PROMOTOR", exp: 9999999999 })
    const res = middleware(makeRequest("/admin", token))
    expect(res.status).toBe(307)
    expect(res.headers.get("location")).toContain("/login")
  })

  it("allows /admin through when role is ADMIN", () => {
    const token = fakeJwt({ sub: "u1", role: "ADMIN", exp: 9999999999 })
    const res = middleware(makeRequest("/admin", token))
    expect(res.headers.get("location")).toBeNull()
  })

  it("allows /analysis through with any valid token", () => {
    const token = fakeJwt({ sub: "u1", role: "PROMOTOR", exp: 9999999999 })
    const res = middleware(makeRequest("/analysis", token))
    expect(res.headers.get("location")).toBeNull()
  })
})
