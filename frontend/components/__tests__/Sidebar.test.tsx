import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import Sidebar from "../nav/Sidebar"

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin/users",
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}))
vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "light", setTheme: vi.fn() }),
}))

/** Two roles, two menus; there is no model page to manage (ADR 0022). */
describe("Sidebar", () => {
  it("gives an admin the platform's pages and no model page", () => {
    render(<Sidebar email="a@example.com" role="admin" />)

    expect(screen.getByText("Użytkownicy")).toBeInTheDocument()
    expect(screen.getByText("Wytyczne")).toBeInTheDocument()
    expect(screen.queryByText("Modele AI")).not.toBeInTheDocument()
  })

  it("does not give a promoter the admin's pages", () => {
    render(<Sidebar email="a@example.com" role="promotor" />)

    expect(screen.queryByText("Użytkownicy")).not.toBeInTheDocument()
    expect(screen.queryByText("Modele AI")).not.toBeInTheDocument()
  })
})
