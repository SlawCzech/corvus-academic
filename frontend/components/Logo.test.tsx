import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import Logo from "./Logo"

describe("Logo", () => {
  it("names the product for screen readers even though the wordmark is a drawing", () => {
    render(<Logo />)
    expect(screen.getByRole("img", { name: "Corvus" })).toBeInTheDocument()
  })
})
