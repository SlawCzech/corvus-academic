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

function mockSave(response: { ok: boolean; status: number; body?: unknown }): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, init?: RequestInit) => {
      if (!init || init.method === undefined) {
        return {
          ok: true,
          json: async () => ({ configured: false, provider: null }),
        } as Response
      }
      return {
        ok: response.ok,
        status: response.status,
        json: async () => response.body,
      } as Response
    }),
  )
}

async function saveKey(): Promise<void> {
  const user = userEvent.setup()
  renderSection()
  await user.type(screen.getByTestId("api-key-input"), "sk-ant-test-key")
  await user.click(screen.getByTestId("save-api-key"))
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

  it("says the provider accepted the key", async () => {
    mockSave({
      ok: true,
      status: 200,
      body: { configured: true, provider: "claude", verified: true },
    })
    await saveKey()
    await waitFor(() => expect(screen.getByTestId("save-ok")).toBeInTheDocument())
  })

  it("says so when the provider rejects the key", async () => {
    mockSave({ ok: false, status: 422, body: { detail: "The provider rejected this key" } })
    await saveKey()
    await waitFor(() =>
      expect(screen.getByTestId("save-rejected")).toHaveTextContent("nie został zapisany"),
    )
    // The typed key stays, so a typo can be fixed in place.
    expect(screen.getByTestId("api-key-input")).toHaveValue("sk-ant-test-key")
  })

  it("says the key is stored unchecked when the provider could not be asked", async () => {
    mockSave({
      ok: true,
      status: 200,
      body: { configured: true, provider: "claude", verified: false },
    })
    await saveKey()
    await waitFor(() => expect(screen.getByTestId("save-unverified")).toBeInTheDocument())
  })

  it("offers removal only when a key is stored", async () => {
    mockStatus(true, "openai")
    renderSection()
    await waitFor(() =>
      expect(screen.getByTestId("remove-api-key")).toBeInTheDocument(),
    )
  })
})
