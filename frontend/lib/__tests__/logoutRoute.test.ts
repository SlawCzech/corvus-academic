import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const jar = new Map<string, string>();

vi.mock("next/headers", () => ({
  cookies: () =>
    Promise.resolve({
      get: (name: string) =>
        jar.has(name) ? { value: jar.get(name) } : undefined,
    }),
}));

import { POST } from "@/app/api/auth/logout/route";

/**
 * Logging out has to reach `app` with the tokens where it reads them —
 * otherwise the cookies go, but the access token stays valid for hours.
 */
describe("POST /api/auth/logout", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    jar.clear();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockReset();
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends the access token as a bearer and the refresh token as a cookie", async () => {
    jar.set("access_token", "acc-1");
    jar.set("refresh_token", "ref-1");

    await POST();

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/auth\/logout$/);
    expect(init.headers).toEqual({
      Authorization: "Bearer acc-1",
      Cookie: "refresh_token=ref-1",
    });
  });

  it("clears both cookies even when app cannot be reached", async () => {
    jar.set("access_token", "acc-1");
    fetchMock.mockRejectedValueOnce(new Error("down"));

    const res = await POST();

    expect(res.status).toBe(200);
    const cleared = res.headers.getSetCookie().join("\n");
    expect(cleared).toMatch(/access_token=;/);
    expect(cleared).toMatch(/refresh_token=;/);
  });

  it("does not call app without any token", async () => {
    await POST();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
