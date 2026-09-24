import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { SWRConfig } from "swr"
import ActionPanel from "../students/ActionPanel"
import type { Student } from "@/lib/api.types"

/**
 * A review started by mistake — say, before the university's guidelines were
 * picked — can be stopped, and the guidelines it will use are in view before
 * it starts.
 */
const STUDENT = {
  id: "s1",
  thesis_type: "bachelor",
  guideline_set_id: null,
} as unknown as Student

const RUNNING = {
  id: "a1",
  student_id: "s1",
  promotor_id: "p1",
  action_type: "generate_review",
  status: "running",
  task_id: "t1",
  detail: null,
  output: null,
  error: null,
  accepted: false,
  accepted_at: null,
  created_at: "2026-09-24T10:00:00Z",
  updated_at: "2026-09-24T10:00:00Z",
}

function json(body: unknown, status = 200): Promise<Response> {
  return Promise.resolve(new Response(JSON.stringify(body), { status }))
}

describe("ActionPanel", () => {
  const fetchMock = vi.fn()
  let cancelled = false

  beforeEach(() => {
    cancelled = false
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith("/cancel")) {
        cancelled = true
        return json({ ...RUNNING, status: "cancelled" })
      }
      if (url === "/api/students/s1/actions" && init?.method === "POST") return json(RUNNING)
      if (url === "/api/students/s1/actions/a1")
        return json(cancelled ? { ...RUNNING, status: "cancelled" } : RUNNING)
      if (url.startsWith("/api/guidelines/")) return json([])
      if (url === "/api/models")
        return json({ backend: "ollama", default: "m", local: [], local_available: true, byok: {} })
      return json({})
    })
    vi.stubGlobal("fetch", fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    fetchMock.mockReset()
  })

  function renderPanel(): void {
    render(
      <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        <ActionPanel student={STUDENT} />
      </SWRConfig>,
    )
  }

  it("shows the guidelines a review will use, and warns about the defaults", async () => {
    renderPanel()

    await userEvent.click(screen.getByRole("button", { name: "Napisz recenzję" }))

    expect(screen.getByRole("combobox", { name: "Zestaw wytycznych" })).toBeInTheDocument()
    expect(screen.getByTestId("default-guidelines")).toBeInTheDocument()
  })

  it("does not show guidelines for an action that does not use them", async () => {
    renderPanel()

    await userEvent.click(screen.getByRole("button", { name: "Zaproponuj temat" }))

    expect(screen.queryByRole("combobox", { name: "Zestaw wytycznych" })).not.toBeInTheDocument()
  })

  it("stops a running action", async () => {
    renderPanel()
    await userEvent.click(screen.getByRole("button", { name: "Napisz recenzję" }))
    await userEvent.click(screen.getByTestId("run-action"))

    await userEvent.click(await screen.findByTestId("cancel-action"))

    await waitFor(() => expect(screen.getByTestId("action-status")).toHaveTextContent("Przerwano"))
    expect(screen.queryByTestId("cancel-action")).not.toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => url === "/api/students/s1/actions/a1/cancel")).toBe(
      true,
    )
  })
})
