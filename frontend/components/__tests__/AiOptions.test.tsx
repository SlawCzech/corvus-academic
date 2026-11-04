import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useState } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { SWRConfig } from "swr"
import ModelSelect from "../ai/ModelSelect"
import ReviewToneChoice from "../ai/ReviewToneChoice"

/**
 * The model is one of the promoter's own keys (ADR 0022), and the tone is
 * picked with the meaning of each option spelled out.
 */
const CATALOG = {
  byok: { claude: "claude-sonnet-5-5", openai: "gpt-6.1-sol" },
}

function stubApi(
  keyStatus: { configured: boolean; providers: string[] },
  catalog: object = CATALOG,
): void {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const body = url === "/api/models" ? catalog : keyStatus
      return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
    }),
  )
}

function Model({ initial = "" }: { initial?: string }) {
  const [value, setValue] = useState(initial)
  return (
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <ModelSelect value={value} onChange={setValue} className="" labelClassName="" />
      <output data-testid="value">{value}</output>
    </SWRConfig>
  )
}

function Tone() {
  const [value, setValue] = useState("auto")
  return (
    <>
      <ReviewToneChoice name="tone" value={value} onChange={setValue} />
      <output data-testid="value">{value}</output>
    </>
  )
}

describe("ModelSelect", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("offers only the promoter's keys", async () => {
    stubApi({ configured: true, providers: ["claude"] })
    render(<Model />)

    expect(
      await screen.findByRole("option", { name: "Claude (Anthropic) · claude-sonnet-5-5" }),
    ).toBeInTheDocument()
    expect(screen.queryByRole("option", { name: /OpenAI/ })).not.toBeInTheDocument()
    expect(screen.getByTestId("model-select")).toHaveValue("byok:claude")
    expect(screen.getByTestId("model-byok")).toBeInTheDocument()
  })

  it("sends a promoter without a key to the profile", async () => {
    stubApi({ configured: false, providers: [] })
    render(<Model />)

    expect(await screen.findByTestId("model-needs-key")).toHaveTextContent(
      "Dodaj klucz w profilu",
    )
    expect(screen.getByRole("link", { name: "Dodaj klucz w profilu" })).toHaveAttribute(
      "href",
      "/profile",
    )
  })

  it("treats a local model saved before ADR 0022 as no choice", async () => {
    stubApi({ configured: true, providers: ["openai"] })
    render(<Model initial="gemma4:12b" />)

    expect(await screen.findByRole("option", { name: "OpenAI · gpt-6.1-sol" })).toBeInTheDocument()
    expect(screen.getByTestId("model-select")).toHaveValue("byok:openai")
  })

  it("lets the promoter pick between two keys", async () => {
    stubApi({ configured: true, providers: ["claude", "openai"] })
    render(<Model />)

    const select = await screen.findByTestId("model-select")
    await screen.findByRole("option", { name: /Claude \(Anthropic\)/ })
    expect(select).toHaveValue("byok:claude")

    await userEvent.selectOptions(select, "byok:openai")
    expect(screen.getByTestId("value")).toHaveTextContent("byok:openai")
  })

  it("does not move a removed key's runs onto the other provider", async () => {
    stubApi({ configured: true, providers: ["claude"] })
    render(<Model initial="byok:openai" />)

    expect(await screen.findByTestId("model-needs-key")).toHaveTextContent(
      "Klucz OpenAI z Twoich ustawień został usunięty",
    )
    expect(screen.getByTestId("model-select")).toHaveValue("")
  })
})

describe("ReviewToneChoice", () => {
  it("is automatic until the promoter chooses to set the tone", async () => {
    render(<Tone />)
    expect(screen.queryByRole("radio", { name: /Powściągliwy/ })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole("radio", { name: "Wybieram sam" }))

    expect(screen.getByText("Spełnia minimum, z wyraźnymi słabościami")).toBeInTheDocument()
    await userEvent.click(screen.getByRole("radio", { name: /Powściągliwy/ }))
    expect(screen.getByTestId("value")).toHaveTextContent("reserved")

    await userEvent.click(screen.getByRole("radio", { name: "Automatyczny" }))
    expect(screen.getByTestId("value")).toHaveTextContent("auto")
  })
})
