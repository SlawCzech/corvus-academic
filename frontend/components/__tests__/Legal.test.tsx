import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import AcceptTermsForm from "@/components/legal/AcceptTermsForm"
import { hideEmail, revealEmail } from "@/components/legal/hiddenEmail"
import Privacy from "@/content/legal/Privacy"
import Terms from "@/content/legal/Terms"
import { operator } from "@/content/legal/operator"

const replace = vi.fn()
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }))

const OPERATOR = { name: "Jan Testowy", email: "kontakt@example.com" }

afterEach(() => {
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
  replace.mockReset()
})

describe("legal documents", () => {
  it("name who runs the service", () => {
    render(<Terms operator={OPERATOR} />)
    expect(screen.getAllByText(/Jan Testowy/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Powierzenie przetwarzania danych/)).toBeTruthy()
  })

  it("promise the retention the code applies", () => {
    render(<Terms operator={OPERATOR} />)
    expect(screen.getByText(/usuwane 14 dni po/)).toBeTruthy()
    expect(screen.getByText(/usuwane 30 dni po zakończeniu/)).toBeTruthy()
  })

  it("keep login events for ninety days", () => {
    render(<Privacy operator={OPERATOR} />)
    expect(screen.getByText("Logi logowań — 90 dni.")).toBeTruthy()
  })

  it("keep the operator's address out of the page until asked", async () => {
    const { container } = render(<Privacy operator={OPERATOR} />)
    expect(container.innerHTML).not.toContain("kontakt@example.com")

    await userEvent.click(screen.getByRole("button", { name: "pokaż adres e-mail" }))

    const link = screen.getByRole("link", { name: "kontakt@example.com" })
    expect(link.getAttribute("href")).toBe("mailto:kontakt@example.com")
  })

  it("encode an address so it comes back whole, whatever it holds", () => {
    for (const email of ["kontakt@example.com", "[adres kontaktowy — OPERATOR_EMAIL]"]) {
      const hidden = hideEmail(email)
      expect(hidden).not.toContain("@")
      expect(revealEmail(hidden)).toBe(email)
    }
  })

  it("show a visible gap when the operator is not configured", () => {
    vi.stubEnv("OPERATOR_NAME", "")
    expect(operator().name).toMatch(/OPERATOR_NAME/)
    vi.stubEnv("OPERATOR_NAME", " Jan Testowy ")
    expect(operator().name).toBe("Jan Testowy")
  })
})

describe("accepting the terms", () => {
  function respond(body: unknown, status = 200): ReturnType<typeof vi.fn> {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }))
    vi.stubGlobal("fetch", fetchMock)
    return fetchMock
  }

  it("waits for the box to be ticked", () => {
    render(<AcceptTermsForm version="v1" next="/students" />)
    expect(screen.getByRole("button", { name: "Akceptuję" })).toHaveProperty("disabled", true)
  })

  it("records the version and goes back where the promoter was", async () => {
    const fetchMock = respond({ current_version: "v1", accepted_at: "2026-11-06T12:00:00Z" })
    render(<AcceptTermsForm version="v1" next="/students/s1" />)

    await userEvent.click(screen.getByRole("checkbox"))
    await userEvent.click(screen.getByRole("button", { name: "Akceptuję" }))

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/students/s1"))
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(JSON.parse(init.body as string)).toEqual({ version: "v1" })
  })

  it("says so when the text changed meanwhile", async () => {
    respond({ detail: "Regulamin zmienił się w międzyczasie. Odśwież stronę." }, 409)
    render(<AcceptTermsForm version="old" next="/students" />)

    await userEvent.click(screen.getByRole("checkbox"))
    await userEvent.click(screen.getByRole("button", { name: "Akceptuję" }))

    expect((await screen.findByTestId("accept-terms-error")).textContent).toMatch(/Odśwież/)
    expect(replace).not.toHaveBeenCalled()
  })
})
