import { render, screen } from "@testing-library/react"
import { renderToString } from "react-dom/server"
import { describe, expect, it, vi } from "vitest"
import Sidebar from "./Sidebar"

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}))
vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "dark", setTheme: vi.fn() }),
}))

describe("Sidebar guide link", () => {
  it("opens the promoter's guide in a new tab", () => {
    render(<Sidebar email="a@b.pl" role="promotor" />)

    const link = screen.getByRole("link", { name: "Przewodnik" })
    expect(link).toHaveAttribute("href", "/przewodnik.pdf")
    expect(link).toHaveAttribute("target", "_blank")
  })

  it("is not in the admin's menu", () => {
    render(<Sidebar email="a@b.pl" role="admin" />)

    expect(screen.queryByRole("link", { name: "Przewodnik" })).not.toBeInTheDocument()
  })
})

describe("Sidebar theme toggle", () => {
  it("renders the light-theme label on the server, which cannot know the theme", () => {
    const html = renderToString(<Sidebar email="a@b.pl" role="promotor" />)

    expect(html).toContain("Ciemny motyw")
    expect(html).not.toContain("Jasny motyw")
  })

  it("shows the real theme once it runs in the browser", () => {
    render(<Sidebar email="a@b.pl" role="promotor" />)

    expect(screen.getByRole("button", { name: "Jasny motyw" })).toBeInTheDocument()
  })
})
