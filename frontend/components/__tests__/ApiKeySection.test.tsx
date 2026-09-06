import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { SWRConfig } from "swr"
import { beforeEach, describe, expect, it, vi } from "vitest"
import ApiKeySection from "../ApiKeySection"

/** A fresh SWR cache per test — otherwise the first status answer sticks. */
function renderSection(): void {
  render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <ApiKeySection />
    </SWRConfig>,
  )
}

function mockStatus(configured: boolean, provider: string | null = null): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, init?: RequestInit) => {
      if (!init || init.method === undefined) {
        return {
          ok: true,
          json: async () => ({ configured, provider }),
        } as Response
      }
      return { ok: true, json: async () => ({ configured: true }) } as Response
    }),
  )
}

describe("ApiKeySection", () => {
  beforeEach(() => {
    mockStatus(false)
  })

  it("says the local model is used when no key is stored", async () => {
    renderSection()
    await waitFor(() =>
      expect(screen.getByTestId("api-key-status")).toHaveTextContent(
        "model lokalny",
      ),
    )
  })

  it("names the provider once a key is stored", async () => {
    mockStatus(true, "claude")
    renderSection()
    await waitFor(() =>
      expect(screen.getByTestId("api-key-status")).toHaveTextContent(
        "Claude (Anthropic)",
      ),
    )
  })

  it("keeps the key hidden until asked", async () => {
    const user = userEvent.setup()
    renderSection()

    const input = screen.getByTestId("api-key-input")
    expect(input).toHaveAttribute("type", "password")
    await user.click(screen.getByTestId("toggle-visibility"))
    expect(input).toHaveAttribute("type", "text")
  })

  it("will not save an empty key", () => {
    renderSection()
    expect(screen.getByTestId("save-api-key")).toBeDisabled()
  })

  it("sends the key and the chosen provider", async () => {
    const user = userEvent.setup()
    renderSection()

    await user.selectOptions(screen.getByTestId("provider-select"), "openai")
    await user.type(screen.getByTestId("api-key-input"), "sk-openai-test")
    await user.click(screen.getByTestId("save-api-key"))

    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls
      const patch = calls.find(([, init]) => init?.method === "PATCH")
      expect(patch).toBeDefined()
      expect(JSON.parse(String(patch![1]!.body))).toEqual({
        api_key: "sk-openai-test",
        provider: "openai",
      })
    })
  })

  it("offers removal only when a key is stored", async () => {
    mockStatus(true, "openai")
    renderSection()
    await waitFor(() =>
      expect(screen.getByTestId("remove-api-key")).toBeInTheDocument(),
    )
  })
})
