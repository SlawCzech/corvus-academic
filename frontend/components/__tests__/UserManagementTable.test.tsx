import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { SWRConfig } from "swr"
import { afterEach, describe, expect, it, vi } from "vitest"
import UserManagementTable from "../UserManagementTable"

const USERS = [
  {
    id: "u-1",
    email: "promotor@example.com",
    role: "promotor",
    created_at: "2026-11-01T10:00:00Z",
  },
]

function stubApi(reset: { status: number; body: unknown }) {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.endsWith("/password-reset") && init?.method === "POST") {
      return Promise.resolve(new Response(JSON.stringify(reset.body), { status: reset.status }))
    }
    if (url === "/api/users") {
      return Promise.resolve(new Response(JSON.stringify(USERS), { status: 200 }))
    }
    return Promise.resolve(new Response("[]", { status: 200 }))
  })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

function renderTable() {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <UserManagementTable />
    </SWRConfig>,
  )
}

afterEach(() => vi.unstubAllGlobals())

describe("UserManagementTable — password reset", () => {
  it("shows the temporary password once, after a confirmation", async () => {
    const fetchMock = stubApi({ status: 200, body: { temporary_password: "Tmp-abc123xyz" } })
    const user = userEvent.setup()
    renderTable()
    await user.click(await screen.findByRole("button", { name: "Resetuj hasło" }))
    expect(fetchMock).not.toHaveBeenCalledWith(
      "/api/users/u-1/password-reset",
      expect.anything(),
    )
    await user.click(screen.getByRole("button", { name: "Tak" }))
    expect(await screen.findByTestId("temporary-password")).toHaveTextContent("Tmp-abc123xyz")
    await user.click(screen.getByRole("button", { name: "Gotowe" }))
    expect(screen.queryByTestId("temporary-password")).not.toBeInTheDocument()
  })

  it("says why a reset was refused", async () => {
    stubApi({ status: 409, body: { detail: "Własne hasło zmień w profilu." } })
    const user = userEvent.setup()
    renderTable()
    await user.click(await screen.findByRole("button", { name: "Resetuj hasło" }))
    await user.click(screen.getByRole("button", { name: "Tak" }))
    expect(await screen.findByText("Własne hasło zmień w profilu.")).toBeInTheDocument()
    expect(screen.queryByTestId("temporary-password")).not.toBeInTheDocument()
  })
})

describe("UserManagementTable — a new account", () => {
  function stubCreate(created: { status: number; body: unknown }) {
    const posted: unknown[] = []
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      if (url === "/api/users" && init?.method === "POST") {
        posted.push(JSON.parse(String(init.body)))
        return Promise.resolve(
          new Response(JSON.stringify(created.body), { status: created.status }),
        )
      }
      if (url === "/api/users") {
        return Promise.resolve(new Response(JSON.stringify(USERS), { status: 200 }))
      }
      return Promise.resolve(new Response("[]", { status: 200 }))
    })
    vi.stubGlobal("fetch", fetchMock)
    return { fetchMock, posted }
  }

  it("asks for no password and shows the temporary one with an invitation", async () => {
    const { posted } = stubCreate({
      status: 201,
      body: {
        id: "u-2",
        email: "nowy@uczelnia.pl",
        role: "promotor",
        created_at: "2026-11-07T10:00:00Z",
        must_change_password: true,
        temporary_password: "Tmp-new123",
      },
    })
    const user = userEvent.setup()
    renderTable()

    await user.click(await screen.findByRole("button", { name: "Dodaj użytkownika" }))
    expect(screen.queryByText("Hasło")).not.toBeInTheDocument()
    await user.type(screen.getByRole("textbox"), "nowy@uczelnia.pl")
    await user.click(screen.getByRole("button", { name: "Utwórz" }))

    expect(await screen.findByTestId("temporary-password")).toHaveTextContent("Tmp-new123")
    expect(posted[0]).not.toHaveProperty("password")
    await user.click(screen.getByRole("button", { name: "Kopiuj zaproszenie" }))
    // user-event's own clipboard stands in for the browser's.
    const copied = await navigator.clipboard.readText()
    expect(copied).toContain("Login: nowy@uczelnia.pl")
    expect(copied).toContain("Hasło tymczasowe: Tmp-new123")
    expect(screen.getByRole("button", { name: "Zaproszenie skopiowane" })).toBeInTheDocument()
  })

  it("keeps the form open with the reason when the email is taken", async () => {
    stubCreate({ status: 409, body: { detail: "Konto z tym adresem już istnieje." } })
    const user = userEvent.setup()
    renderTable()

    await user.click(await screen.findByRole("button", { name: "Dodaj użytkownika" }))
    await user.type(screen.getByRole("textbox"), "promotor@example.com")
    await user.click(screen.getByRole("button", { name: "Utwórz" }))

    expect(await screen.findByText("Konto z tym adresem już istnieje.")).toBeInTheDocument()
    expect(screen.queryByTestId("temporary-password")).not.toBeInTheDocument()
  })
})

describe("UserManagementTable — reset", () => {
  it("offers no invitation after a reset", async () => {
    stubApi({ status: 200, body: { temporary_password: "Tmp-abc123xyz" } })
    const user = userEvent.setup()
    renderTable()
    await user.click(await screen.findByRole("button", { name: "Resetuj hasło" }))
    await user.click(screen.getByRole("button", { name: "Tak" }))
    await screen.findByTestId("temporary-password")
    expect(screen.queryByRole("button", { name: "Kopiuj zaproszenie" })).not.toBeInTheDocument()
  })
})
