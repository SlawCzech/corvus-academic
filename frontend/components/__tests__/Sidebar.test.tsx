import { render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { SWRConfig } from "swr"
import Sidebar from "../nav/Sidebar"

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin/users",
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}))
vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "light", setTheme: vi.fn() }),
}))

/**
 * With local models off there is nothing to manage on the admin's model page,
 * so the menu drops it (ADR 0016). A promoter never asks about it.
 */
function stubCatalog(localEnabled: boolean) {
  const fetchMock = vi.fn(async () =>
    new Response(
      JSON.stringify({ local_available: true, local_enabled: localEnabled, models: [] }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  )
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

function renderSidebar(role: string) {
  render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <Sidebar email="a@example.com" role={role} />
    </SWRConfig>,
  )
}

describe("Sidebar", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("drops the model page for an admin when local models are off", async () => {
    const fetchMock = stubCatalog(false)
    renderSidebar("admin")
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    await waitFor(() => expect(screen.queryByText("Modele AI")).not.toBeInTheDocument())
    expect(screen.getByText("Użytkownicy")).toBeInTheDocument()
  })

  it("keeps the model page for an admin when local models are on", async () => {
    const fetchMock = stubCatalog(true)
    renderSidebar("admin")
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(await screen.findByText("Modele AI")).toBeInTheDocument()
  })

  it("does not ask a promoter's browser for the admin catalog", () => {
    const fetchMock = stubCatalog(true)
    renderSidebar("promotor")
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.queryByText("Modele AI")).not.toBeInTheDocument()
  })
})
