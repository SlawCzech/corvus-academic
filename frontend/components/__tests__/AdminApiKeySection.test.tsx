import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import AdminApiKeySection from "../AdminApiKeySection"

describe("AdminApiKeySection", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn())
  })

  it("renders LOCAL and CLOUD radio buttons", () => {
    render(<AdminApiKeySection />)
    expect(screen.getByTestId("radio-local")).toBeInTheDocument()
    expect(screen.getByTestId("radio-cloud")).toBeInTheDocument()
    expect(screen.getByTestId("radio-local")).toBeChecked()
  })

  it("hides API key field when LOCAL is selected", () => {
    render(<AdminApiKeySection />)
    expect(screen.queryByTestId("api-key-input")).not.toBeInTheDocument()
  })

  it("shows API key field when CLOUD is selected", async () => {
    const user = userEvent.setup()
    render(<AdminApiKeySection />)
    await user.click(screen.getByTestId("radio-cloud"))
    expect(screen.getByTestId("api-key-input")).toBeInTheDocument()
  })

  it("toggles API key visibility", async () => {
    const user = userEvent.setup()
    render(<AdminApiKeySection />)
    await user.click(screen.getByTestId("radio-cloud"))
    const input = screen.getByTestId("api-key-input")
    expect(input).toHaveAttribute("type", "password")
    await user.click(screen.getByTestId("toggle-visibility"))
    expect(input).toHaveAttribute("type", "text")
    await user.click(screen.getByTestId("toggle-visibility"))
    expect(input).toHaveAttribute("type", "password")
  })

  it("submits api key via PATCH /api/admin/api-key", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    )
    const user = userEvent.setup()
    render(<AdminApiKeySection />)
    await user.click(screen.getByTestId("radio-cloud"))
    await user.type(screen.getByTestId("api-key-input"), "sk-test-key")
    await user.click(screen.getByTestId("save-api-key"))
    await waitFor(() =>
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        "/api/admin/api-key",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ api_key: "sk-test-key", provider: "claude" }),
        }),
      ),
    )
    expect(await screen.findByTestId("save-success")).toBeInTheDocument()
  })

  it("shows error message when save fails", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ error: "Unauthorized" }), { status: 401 }),
    )
    const user = userEvent.setup()
    render(<AdminApiKeySection />)
    await user.click(screen.getByTestId("radio-cloud"))
    await user.type(screen.getByTestId("api-key-input"), "sk-bad")
    await user.click(screen.getByTestId("save-api-key"))
    expect(await screen.findByTestId("save-error")).toBeInTheDocument()
  })

  it("save button is disabled when LOCAL backend is selected", () => {
    render(<AdminApiKeySection />)
    expect(screen.getByTestId("save-api-key")).toBeDisabled()
  })
})
