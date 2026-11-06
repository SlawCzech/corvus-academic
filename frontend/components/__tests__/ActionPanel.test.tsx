import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { SWRConfig } from "swr"
import ActionPanel from "../students/ActionPanel"
import type { Student } from "@/lib/api.types"

/**
 * A review started by mistake can be stopped, and the guidelines it will use
 * are in view before it starts — without them it does not start at all.
 */
const STUDENT = {
  id: "s1",
  thesis_type: "bachelor",
  guideline_set_id: "g1",
} as unknown as Student

const WITHOUT_GUIDELINES = { ...STUDENT, guideline_set_id: null } as Student

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
  let keys: string[] = []
  // What the student's action list holds when the panel opens.
  let listed: unknown[] = []
  // Resolved when the list may arrive; by default it arrives at once.
  let listGate: Promise<void> = Promise.resolve()

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
    keys = ["claude"]
    listed = []
    listGate = Promise.resolve()
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
      if (url === "/api/students/s1/actions") return listGate.then(() => json(listed))
      if (url.startsWith("/api/guidelines/"))
        return json([
          {
            id: "g1",
            name: "Prace licencjackie",
            thesis_type: "bachelor",
            university: { id: "u1", name: "UE Katowice", short_name: "UE" },
            current: { id: "v1", version_no: 1 },
            has_draft: false,
          },
        ])
      if (url === "/api/settings/api-key/status")
        return json({ configured: keys.length > 0, providers: keys })
      if (url === "/api/models")
        return json({ byok: {} })
      return json({})
    })
    vi.stubGlobal("fetch", fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    fetchMock.mockReset()
  })

  function renderPanel(student: Student = STUDENT): void {
    render(
      <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        <ActionPanel student={student} />
      </SWRConfig>,
    )
  }

  it("shows the guidelines a review will use", async () => {
    renderPanel()

    await userEvent.click(screen.getByRole("button", { name: "Recenzja finalna" }))

    expect(screen.getByRole("combobox", { name: "Zestaw wytycznych" })).toBeInTheDocument()
    expect(screen.queryByTestId("missing-guidelines")).not.toBeInTheDocument()
    expect(screen.getByTestId("run-action")).toBeEnabled()
  })

  it("does not start a review before the university's guidelines are chosen", async () => {
    renderPanel(WITHOUT_GUIDELINES)

    await userEvent.click(screen.getByRole("button", { name: "Recenzja finalna" }))

    expect(screen.getByTestId("missing-guidelines")).toBeInTheDocument()
    expect(screen.getByTestId("run-action")).toBeDisabled()
  })

  it("starts an action that judges nothing against the guidelines without them", async () => {
    renderPanel(WITHOUT_GUIDELINES)

    await userEvent.click(screen.getByRole("button", { name: "Zaproponuj temat" }))

    await waitFor(() => expect(screen.getByTestId("run-action")).toBeEnabled())
  })

  it("does not show guidelines for an action that does not use them", async () => {
    renderPanel()

    await userEvent.click(screen.getByRole("button", { name: "Zaproponuj temat" }))

    expect(screen.queryByRole("combobox", { name: "Zestaw wytycznych" })).not.toBeInTheDocument()
  })

  function triggerBody(): Record<string, unknown> {
    const trigger = fetchMock.mock.calls.find(
      ([url, init]) => url === "/api/students/s1/actions" && init?.method === "POST",
    )
    return JSON.parse(String(trigger?.[1]?.body)) as Record<string, unknown>
  }

  it("waits for a key when the promoter has none", async () => {
    keys = []
    renderPanel()
    await userEvent.click(screen.getByRole("button", { name: "Zaproponuj temat" }))

    expect(await screen.findByTestId("model-needs-key")).toBeInTheDocument()
    expect(screen.getByTestId("run-action")).toBeDisabled()
  })

  it("says the run goes on the promoter's key, and sends that provider", async () => {
    keys = ["openai"]
    renderPanel()
    await userEvent.click(screen.getByRole("button", { name: "Zaproponuj temat" }))

    // The model choice is in view without opening anything.
    expect(await screen.findByTestId("model-byok")).toBeInTheDocument()
    expect(screen.getByTestId("model-select")).toHaveDisplayValue(/OpenAI/)
    await userEvent.click(screen.getByTestId("run-action"))

    await waitFor(() => expect(triggerBody().provider).toBe("openai"))
    expect(triggerBody()).not.toHaveProperty("model")
  })

  it("stops a running action", async () => {
    renderPanel()
    await userEvent.click(screen.getByRole("button", { name: "Recenzja finalna" }))
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
    await userEvent.click(screen.getByRole("button", { name: "Recenzja finalna" }))
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

  it("keeps the model choice in view without opening anything", async () => {
    renderPanel()

    await userEvent.click(screen.getByRole("button", { name: "Zaproponuj temat" }))

    expect(screen.getByTestId("model-select")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Opcje/ })).not.toBeInTheDocument()
  })

  it("opens on the action that was running when the promoter left", async () => {
    listed = [RUNNING]
    renderPanel()

    // Nobody clicked anything: the review started earlier is back in view,
    // followed again, and can be stopped from here.
    expect(await screen.findByTestId("action-status")).toHaveTextContent("Liczy się")
    expect(screen.getByTestId("cancel-action")).toBeInTheDocument()
    expect(screen.getByTestId("unfinished-generate_review")).toBeInTheDocument()
  })

  it("comes back to a review waiting for the promoter's findings", async () => {
    paused = true
    listed = [PAUSED]
    renderPanel()

    expect(await screen.findAllByTestId("finding-toggle")).toHaveLength(2)
  })

  it("leaves the promoter's own choice alone when the list arrives late", async () => {
    listed = [RUNNING]
    let arrive: () => void = () => {}
    listGate = new Promise((resolve) => {
      arrive = resolve
    })
    renderPanel()
    await userEvent.click(screen.getByRole("button", { name: "Zaproponuj temat" }))
    arrive()

    await screen.findByTestId("unfinished-generate_review")
    // Still on what they picked, not pulled over to the running review.
    expect(screen.getByTestId("run-action")).toBeEnabled()
    expect(screen.queryByTestId("action-status")).not.toBeInTheDocument()
  })

  it("groups the tiles by the stage of the work", () => {
    renderPanel()

    const stage = screen.getByRole("region", { name: "Gotowa całość" })
    expect(within(stage).getByRole("button", { name: "Recenzja finalna" })).toBeInTheDocument()
    expect(within(stage).queryByRole("button", { name: "Pytania na obronę" })).toBeNull()
    expect(screen.getAllByRole("region")).toHaveLength(3)
  })

  it("offers every action as a tile, and shrinks them to a strip once one is chosen", async () => {
    renderPanel()

    expect(screen.getByTestId("action-tiles")).toHaveTextContent(
      "Czy cytowane prace istnieją",
    )
    await userEvent.click(screen.getByRole("button", { name: "Sprawdź bibliografię" }))

    expect(screen.queryByTestId("action-tiles")).not.toBeInTheDocument()
    expect(screen.getByTestId("run-action")).toBeInTheDocument()
    // And back to the whole catalogue.
    await userEvent.click(screen.getByRole("button", { name: "Wszystkie akcje" }))
    expect(screen.getByTestId("action-tiles")).toBeInTheDocument()
  })

  it("opens on the action a suggestion elsewhere led to", () => {
    render(
      <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        <ActionPanel student={STUDENT} initialType="verify_bibliography" />
      </SWRConfig>,
    )

    expect(screen.queryByTestId("action-tiles")).not.toBeInTheDocument()
    expect(screen.getByTestId("run-action")).toBeInTheDocument()
  })

  it("says after a review that the references were not checked, and leads there", async () => {
    const REVIEWED = {
      ...RUNNING,
      status: "completed",
      output: { findings: [], scores: [], summary: "ok", recommendation: "Dopuścić" },
    }
    listed = [REVIEWED]
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url === "/api/students/s1/actions" && init?.method === "POST") return json(REVIEWED)
      if (url === "/api/students/s1/actions") return json(listed)
      if (url === "/api/students/s1/actions/a1") return json(REVIEWED)
      if (url === "/api/settings/api-key/status") return json({ configured: true, providers: ["claude"] })
      if (url === "/api/models")
        return json({ byok: {} })
      if (url.startsWith("/api/guidelines/"))
        return json([
          {
            id: "g1",
            name: "Prace licencjackie",
            thesis_type: "bachelor",
            university: { id: "u1", name: "UE Katowice", short_name: "UE" },
            current: { id: "v1", version_no: 1 },
            has_draft: false,
          },
        ])
      return json({})
    })
    render(
      <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        <ActionPanel student={STUDENT} initialType="generate_review" />
      </SWRConfig>,
    )
    await userEvent.click(screen.getByTestId("run-action"))

    const hint = await screen.findByTestId("suggest-bibliography")
    expect(hint).toHaveTextContent("nie sprawdza, czy cytowane prace istnieją")
    await userEvent.click(
      screen.getAllByRole("button", { name: "Sprawdź bibliografię" }).at(-1)!,
    )
    expect(screen.queryByTestId("suggest-bibliography")).not.toBeInTheDocument()
  })

  it("offers both reviews and says what the final one will read", async () => {
    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <ActionPanel student={STUDENT} notes={{ generate_review: "Oceni wersję 2." }} />
      </SWRConfig>,
    )

    await userEvent.click(screen.getByRole("button", { name: "Recenzja próbna" }))
    expect(screen.queryByTestId("action-note")).not.toBeInTheDocument()
    expect(screen.getByTestId("findings-first")).toBeInTheDocument()
    expect(screen.queryByText("Ton recenzji")).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Recenzja finalna" }))
    expect(screen.getByTestId("action-note")).toHaveTextContent("Oceni wersję 2.")
    expect(screen.getByText("Ton recenzji")).toBeInTheDocument()
  })
})
