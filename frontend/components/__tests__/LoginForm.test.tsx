import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"

const { mockPush } = vi.hoisted(() => ({ mockPush: vi.fn() }))

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}))

import LoginForm from "../LoginForm"

describe("LoginForm", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal("fetch", vi.fn())
  })

  it("renders email and password fields", () => {
    render(<LoginForm />)
    expect(screen.getByTestId("email-input")).toBeInTheDocument()
    expect(screen.getByTestId("password-input")).toBeInTheDocument()
    expect(screen.getByTestId("submit-button")).toBeInTheDocument()
  })

  it("shows validation error for invalid email", async () => {
    const user = userEvent.setup()
    render(<LoginForm />)
    await user.type(screen.getByTestId("email-input"), "notanemail")
    await user.click(screen.getByTestId("submit-button"))
    expect(await screen.findByTestId("email-error")).toHaveTextContent(
      /valid email/i,
    )
  })

  it("shows validation error when password is too short", async () => {
    const user = userEvent.setup()
    render(<LoginForm />)
    await user.type(screen.getByTestId("email-input"), "user@example.com")
    await user.type(screen.getByTestId("password-input"), "short")
    await user.click(screen.getByTestId("submit-button"))
    expect(await screen.findByTestId("password-error")).toHaveTextContent(
      /8 characters/i,
    )
  })

  it("calls /api/auth/login and redirects on success", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    )
    const user = userEvent.setup()
    render(<LoginForm />)
    await user.type(screen.getByTestId("email-input"), "admin@example.com")
    await user.type(screen.getByTestId("password-input"), "password123")
    await user.click(screen.getByTestId("submit-button"))
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/analysis"))
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      "/api/auth/login",
      expect.objectContaining({ method: "POST" }),
    )
  })

  it("shows server error on failed login", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ error: "Invalid credentials" }), {
        status: 401,
      }),
    )
    const user = userEvent.setup()
    render(<LoginForm />)
    await user.type(screen.getByTestId("email-input"), "admin@example.com")
    await user.type(screen.getByTestId("password-input"), "wrongpassword")
    await user.click(screen.getByTestId("submit-button"))
    expect(await screen.findByTestId("server-error")).toHaveTextContent(
      /invalid email or password/i,
    )
    expect(mockPush).not.toHaveBeenCalled()
  })
})
