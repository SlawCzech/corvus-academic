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
  let paused = false
  let resumed = false

  const PAUSED = {
    ...RUNNING,
    status: "awaiting_input",
    output: {
      findings: [
        { section: "Wstęp", description: "Brak hipotez", severity: "critical", suggestion: "-", quote: "" },
        { section: "3.1", description: "Próba nieopisana", severity: "major", suggestion: "-", quote: "ankieta wśród znajomych" },
      ],
      scores: [],
      summary: null,
      recommendation: null,
      status: "running",
      error: null,
    },
  }

  beforeEach(() => {
    cancelled = false
    paused = false
    resumed = false
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith("/resume")) {
        resumed = true
        return json({ ...RUNNING, status: "pending" })
      }
      if (url.endsWith("/cancel")) {
        cancelled = true
        return json({ ...RUNNING, status: "cancelled" })
      }
      if (url === "/api/students/s1/actions" && init?.method === "POST") return json(RUNNING)
      if (url === "/api/students/s1/actions/a1") {
        if (cancelled) return json({ ...RUNNING, status: "cancelled" })
        if (paused && !resumed) return json(PAUSED)
        return json(RUNNING)
      }
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

  it("asks for the findings first, then writes the review from the ones kept", async () => {
    paused = true
    renderPanel()
    await userEvent.click(screen.getByRole("button", { name: "Napisz recenzję" }))
    await userEvent.click(screen.getByTestId("findings-first"))
    await userEvent.click(screen.getByTestId("run-action"))

    const trigger = fetchMock.mock.calls.find(
      ([url, init]) => url === "/api/students/s1/actions" && init?.method === "POST",
    )
    expect(JSON.parse(String(trigger?.[1]?.body)).review_findings_first).toBe(true)

    const toggles = await screen.findAllByTestId("finding-toggle")
    expect(toggles).toHaveLength(2)
    await userEvent.click(toggles[0])
    await userEvent.click(screen.getByTestId("resume-action"))

    const resume = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/resume"))
    expect(JSON.parse(String(resume?.[1]?.body))).toEqual({ accepted_findings: [1] })
  })
})
