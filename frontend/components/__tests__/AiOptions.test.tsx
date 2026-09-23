import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useState } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { SWRConfig } from "swr"
import ModelSelect from "../ai/ModelSelect"
import ReviewToneChoice from "../ai/ReviewToneChoice"

/**
 * The model used to be a free-text Ollama tag and the tone a bare dropdown
 * with no word on what "Powściągliwy" means. Both are now picked from what
 * is actually there, with the meaning spelled out.
 */
const CATALOG = {
  default: "qwen3:30b-a3b",
  available: [
    { name: "gemma4:12b", parameter_size: "11.9B" },
    { name: "qwen3:30b-a3b", parameter_size: "30.5B" },
  ],
  local_available: true,
  byok: { claude: "claude-sonnet-4-20250514", openai: "gpt-4o" },
}

function stubApi(keyStatus: { configured: boolean; provider: string | null }): void {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const body = url === "/api/models" ? CATALOG : keyStatus
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

  it("offers the installed models, with the server default first", async () => {
    stubApi({ configured: false, provider: null })
    render(<Model />)

    const select = await screen.findByTestId("model-select")
    expect(await screen.findByRole("option", { name: "Domyślny (qwen3:30b-a3b)" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "gemma4:12b · 11.9B" })).toBeInTheDocument()
    // The default is not listed twice.
    expect(screen.queryByRole("option", { name: /^qwen3:30b-a3b/ })).not.toBeInTheDocument()

    await userEvent.selectOptions(select, "gemma4:12b")
    expect(screen.getByTestId("value")).toHaveTextContent("gemma4:12b")
  })

  it("falls back to the default when a saved model was withdrawn, and says so", async () => {
    stubApi({ configured: false, provider: null })
    render(<Model initial="llama2:7b" />)

    expect(await screen.findByTestId("model-withdrawn")).toHaveTextContent(
      "Model llama2:7b z Twoich ustawień nie jest już dostępny",
    )
    expect(screen.getByTestId("model-select")).toHaveValue("")
    expect(screen.queryByRole("option", { name: /llama2/ })).not.toBeInTheDocument()
  })

  it("names the provider's model instead of a list when the promoter has a key", async () => {
    stubApi({ configured: true, provider: "openai" })
    render(<Model />)

    expect(await screen.findByTestId("model-byok")).toHaveTextContent("OpenAI · gpt-4o")
    expect(screen.queryByTestId("model-select")).not.toBeInTheDocument()
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
