import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import ChangePasswordForm from "../ChangePasswordForm"

const { replace, refresh } = vi.hoisted(() => ({ replace: vi.fn(), refresh: vi.fn() }))
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, refresh }),
}))

/** The backend's refusal reaches the form in its own words. */
async function submit() {
  const user = userEvent.setup()
  const { container } = render(<ChangePasswordForm />)
  const [current, next, confirm] = container.querySelectorAll("input")
  await user.type(current, "wrong-password")
  await user.type(next, "new-secure-password")
  await user.type(confirm, "new-secure-password")
  await user.click(screen.getByRole("button", { name: "Zmień hasło" }))
}

function respondWith(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }))
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

describe("ChangePasswordForm", () => {
  it("sends the current password along with the new one", async () => {
    const fetchMock = respondWith(200, { ok: true })
    await submit()
    expect(await screen.findByText("Hasło zostało zmienione.")).toBeInTheDocument()
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(JSON.parse(init.body as string)).toEqual({
      current_password: "wrong-password",
      new_password: "new-secure-password",
    })
  })

  it("shows why the change was refused", async () => {
    respondWith(403, { detail: "Aktualne hasło jest nieprawidłowe." })
    await submit()
    expect(await screen.findByText("Aktualne hasło jest nieprawidłowe.")).toBeInTheDocument()
  })

  it("falls back to a general message without a reason", async () => {
    respondWith(500, {})
    await submit()
    expect(await screen.findByText("Zmiana hasła nie powiodła się.")).toBeInTheDocument()
  })

  it("asks for the temporary password and moves on once it is replaced", async () => {
    respondWith(200, { ok: true })
    const user = userEvent.setup()
    const { container } = render(<ChangePasswordForm temporaryThen="/dashboard" />)
    expect(screen.getByText("Hasło tymczasowe")).toBeInTheDocument()
    const [current, next, confirm] = container.querySelectorAll("input")
    await user.type(current, "temporary-pass")
    await user.type(next, "my-own-password")
    await user.type(confirm, "my-own-password")
    await user.click(screen.getByRole("button", { name: "Ustaw hasło" }))
    await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"))
    expect(refresh).toHaveBeenCalled()
  })
})
