import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { SWRConfig } from "swr"
import ModelAdmin from "../admin/ModelAdmin"

/**
 * The admin decides which installed models promoters may pick. The default
 * can't be withdrawn from the UI — there would be nothing to fall back on.
 */
function catalog(defaultName: string, enabled: string[]) {
  return {
    local_available: true,
    server_default: "qwen3:30b-a3b",
    models: ["gemma4:12b", "qwen3:30b-a3b"].map((name) => ({
      name,
      parameter_size: null,
      installed: true,
      enabled: name === defaultName || enabled.includes(name),
      is_default: name === defaultName,
    })),
  }
}

let calls: { url: string; method: string; body: unknown }[] = []

describe("ModelAdmin", () => {
  beforeEach(() => {
    calls = []
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET"
        const body: unknown = init?.body ? JSON.parse(init.body as string) : null
        calls.push({ url, method, body })
        const next =
          method === "PATCH"
            ? catalog("qwen3:30b-a3b", ["gemma4:12b"])
            : method === "PUT"
              ? catalog("gemma4:12b", [])
              : catalog("qwen3:30b-a3b", [])
        return Promise.resolve(new Response(JSON.stringify(next), { status: 200 }))
      }),
    )
  })

  afterEach(() => vi.unstubAllGlobals())

  function renderAdmin(): void {
    render(
      <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        <ModelAdmin />
      </SWRConfig>,
    )
  }

  it("keeps the default's toggle locked", async () => {
    renderAdmin()
    const defaultToggle = await screen.findByRole("checkbox", { name: "Udostępnij qwen3:30b-a3b" })
    expect(defaultToggle).toBeChecked()
    expect(defaultToggle).toBeDisabled()
  })

  it("offers a model to promoters", async () => {
    renderAdmin()
    await userEvent.click(await screen.findByRole("checkbox", { name: "Udostępnij gemma4:12b" }))

    await waitFor(() =>
      expect(screen.getByRole("checkbox", { name: "Udostępnij gemma4:12b" })).toBeChecked(),
    )
    expect(calls).toContainEqual({
      url: "/api/admin/models",
      method: "PATCH",
      body: { name: "gemma4:12b", enabled: true },
    })
  })

  it("moves the default", async () => {
    renderAdmin()
    await userEvent.click(
      await screen.findByRole("radio", { name: "Ustaw gemma4:12b jako domyślny" }),
    )

    await waitFor(() =>
      expect(screen.getByRole("radio", { name: "Ustaw gemma4:12b jako domyślny" })).toBeChecked(),
    )
    expect(calls).toContainEqual({
      url: "/api/admin/models/default",
      method: "PUT",
      body: { name: "gemma4:12b" },
    })
  })
})
