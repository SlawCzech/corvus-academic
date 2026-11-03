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
          json: async () => ({ configured: false, providers: [] }),
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

function mockStatus(providers: string[]): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, init?: RequestInit) => {
      if (!init || init.method === undefined) {
        return {
          ok: true,
          json: async () => ({ configured: providers.length > 0, providers }),
        } as Response
      }
      return { ok: true, json: async () => ({ configured: true }) } as Response
    }),
  )
}

describe("ApiKeySection", () => {
  beforeEach(() => {
    mockStatus([])
  })

  it("says a key is needed to run anything when none is stored", async () => {
    renderSection()
    await waitFor(() =>
      expect(screen.getByTestId("api-key-status")).toHaveTextContent(
        "dodaj klucz, żeby uruchamiać akcje AI",
      ),
    )
  })

  it("names the provider once a key is stored", async () => {
    mockStatus(["claude"])
    renderSection()
    await waitFor(() =>
      expect(screen.getByTestId("api-key-status")).toHaveTextContent(
        "Claude (Anthropic)",
      ),
    )
    expect(screen.queryByTestId("stored-key-openai")).not.toBeInTheDocument()
  })

  it("lists both keys when both providers have one", async () => {
    mockStatus(["claude", "openai"])
    renderSection()
    await waitFor(() => expect(screen.getByTestId("stored-key-claude")).toBeInTheDocument())
    expect(screen.getByTestId("stored-key-openai")).toHaveTextContent("OpenAI")
  })

  it("removes one provider's key and leaves the other", async () => {
    const user = userEvent.setup()
    mockStatus(["claude", "openai"])
    renderSection()

    await user.click(await screen.findByTestId("remove-api-key-openai"))

    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls
      const removal = calls.find(([, init]) => init?.method === "DELETE")
      expect(removal?.[0]).toBe("/api/settings/api-key/openai")
    })
  })

  it("says it will replace the key when that provider already has one", async () => {
    const user = userEvent.setup()
    mockStatus(["openai"])
    renderSection()
    await screen.findByTestId("stored-key-openai")

    expect(screen.getByTestId("save-api-key")).toHaveTextContent("Zapisz klucz")
    await user.selectOptions(screen.getByTestId("provider-select"), "openai")
    expect(screen.getByTestId("save-api-key")).toHaveTextContent("Zastąp klucz")
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
      body: { configured: true, providers: ["claude"], verified: true },
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

  it("shows what the provider said about a key it refused", async () => {
    mockSave({
      ok: false,
      status: 422,
      body: {
        detail: "The provider rejected this key",
        provider_message: "This API key is not scoped to a workspace",
      },
    })
    await saveKey()
    await waitFor(() =>
      expect(screen.getByTestId("provider-message")).toHaveTextContent(
        "This API key is not scoped to a workspace",
      ),
    )
    expect(screen.getByTestId("save-rejected")).not.toHaveTextContent("skopiowany")
  })

  it("says the key is stored unchecked when the provider could not be asked", async () => {
    mockSave({
      ok: true,
      status: 200,
      body: { configured: true, providers: ["claude"], verified: false },
    })
    await saveKey()
    await waitFor(() => expect(screen.getByTestId("save-unverified")).toBeInTheDocument())
  })

  it("offers removal only for a provider with a stored key", async () => {
    mockStatus(["openai"])
    renderSection()
    await waitFor(() =>
      expect(screen.getByTestId("remove-api-key-openai")).toBeInTheDocument(),
    )
    expect(screen.queryByTestId("remove-api-key-claude")).not.toBeInTheDocument()
  })
})
