import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { acceptTerms, fetcher } from "@/lib/api.client"

/**
 * The session used to die silently: a fifteen-minute access token expired
 * while a review was running, every call came back 401, and the page reported
 * it as "Nie znaleziono studenta". These cover the renewal that replaced that.
 */
describe("api client session renewal", () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock)
    fetchMock.mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  function json(body: unknown, status = 200): Response {
    return new Response(JSON.stringify(body), { status })
  }

  it("renews the session on 401 and retries the call once", async () => {
    fetchMock
      .mockResolvedValueOnce(json({ detail: "Not authenticated" }, 401))
      .mockResolvedValueOnce(json({ ok: true }))
      .mockResolvedValueOnce(json({ id: "s1", full_name: "Julia Krzemień" }))

    const student = await fetcher<{ full_name: string }>("/api/students/s1")

    expect(student.full_name).toBe("Julia Krzemień")
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock.mock.calls[1][0]).toBe("/api/auth/refresh")
  })

  it("does not renew anything when the call succeeded", async () => {
    fetchMock.mockResolvedValueOnce(json({ id: "s1" }))

    await fetcher("/api/students/s1")

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it("sends the browser to the login page when renewal is refused", async () => {
    const assign = vi.fn()
    vi.stubGlobal("window", { location: { assign } })
    fetchMock
      .mockResolvedValueOnce(json({ detail: "Not authenticated" }, 401))
      .mockResolvedValueOnce(json({ error: "Refresh failed" }, 401))

    await expect(fetcher("/api/students/s1")).rejects.toThrow()
    expect(assign).toHaveBeenCalledWith("/login")
  })

  it("renews once when several calls hit an expired token together", async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url === "/api/auth/refresh") return Promise.resolve(json({ ok: true }))
      const refreshed = fetchMock.mock.calls.some(
        (call) => call[0] === "/api/auth/refresh",
      )
      return Promise.resolve(refreshed ? json({ id: "s1" }) : json({}, 401))
    })

    await Promise.all([
      fetcher("/api/students/s1"),
      fetcher("/api/students/s1/drafts"),
      fetcher("/api/students/s1/actions"),
    ])

    const refreshes = fetchMock.mock.calls.filter(
      (call) => call[0] === "/api/auth/refresh",
    )
    expect(refreshes).toHaveLength(1)
  })
})

/**
 * A promoter who has not accepted the terms in force gets a 403 from every
 * route with student data; the client turns it into the terms page.
 */
describe("api client terms gate", () => {
  const fetchMock = vi.fn()
  const assign = vi.fn()

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock)
    vi.stubGlobal("window", {
      location: { assign, pathname: "/students/s1", search: "?tab=notes" },
    })
    fetchMock.mockReset()
    assign.mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  function json(body: unknown, status = 200): Response {
    return new Response(JSON.stringify(body), { status })
  }

  it("sends the promoter to the terms and back to the page after", async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: "terms_not_accepted" }, 403))

    await expect(fetcher("/api/students/s1")).rejects.toThrow()

    expect(assign).toHaveBeenCalledWith(
      `/terms/accept?next=${encodeURIComponent("/students/s1?tab=notes")}`,
    )
  })

  it("leaves any other 403 to the page", async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: "Admin role required" }, 403))

    await expect(fetcher("/api/admin/users")).rejects.toThrow("Admin role required")

    expect(assign).not.toHaveBeenCalled()
  })

  it("accepts the version the promoter read", async () => {
    fetchMock.mockResolvedValueOnce(json({ current_version: "v1", accepted_at: "now" }))

    await acceptTerms("v1")

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("/api/users/me/terms")
    expect(JSON.parse(init.body as string)).toEqual({ version: "v1" })
  })

  it("says why an acceptance was refused", async () => {
    fetchMock.mockResolvedValueOnce(
      json({ detail: "Regulamin zmienił się w międzyczasie. Odśwież stronę." }, 409),
    )

    await expect(acceptTerms("old")).rejects.toThrow("Odśwież stronę")
  })
})
