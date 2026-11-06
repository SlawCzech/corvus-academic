import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { SWRConfig } from "swr"
import StudentDetail from "../students/StudentDetail"

const mockPush = vi.fn()
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}))

/**
 * Finished actions are stored whole — status, findings, scores, review text —
 * and the history list used to show only "Recenzja · gotowe · 12.09.2026".
 * The result was in the database and out of reach.
 */
const STUDENT = {
  id: "s1",
  promotor_id: "p1",
  full_name: "Julia Krzemień",
  field_of_study: "Zarządzanie",
  thesis_type: "master_article",
  current_topic: "Wpływ FOMO na zakupy impulsywne",
  status: "active",
  created_at: "2026-03-01T10:00:00Z",
  updated_at: "2026-03-01T10:00:00Z",
}

const REVIEW = {
  id: "a1",
  student_id: "s1",
  promotor_id: "p1",
  action_type: "generate_review",
  status: "completed",
  task_id: "t1",
  detail: null,
  output: {
    summary: "Praca spełnia wymagania stawiane pracom dyplomowym.",
    recommendation: "Dopuścić do obrony",
    scores: [{ criteria: "Struktura i spójność", points: 8, max_points: 10 }],
    findings: [],
  },
  error: null,
  accepted: false,
  accepted_at: null,
  created_at: "2026-09-12T12:35:00Z",
  updated_at: "2026-09-12T12:44:00Z",
}

function renderDetail(): void {
  render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <StudentDetail studentId="s1" />
    </SWRConfig>,
  )
}

/**
 * The history list lives behind the student's "Historia" sub-nav section
 * now — it is not the page's default view (that's "Przegląd"), so every
 * test that wants to see it has to switch there first.
 */
async function openHistorySection(): Promise<void> {
  const historyLink = await screen.findByRole("button", { name: "Historia" })
  await userEvent.click(historyLink)
}

describe("StudentDetail — action history", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        const body = url.endsWith("/actions")
          ? [REVIEW]
          : url.endsWith("/meeting-notes") ||
              url.endsWith("/drafts") ||
              url.includes("/guidelines/")
            ? []
            : STUDENT
        return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("opens a past review from the history and shows what it said", async () => {
    renderDetail()
    await openHistorySection()
    const entry = await screen.findByRole("button", { name: /Recenzja/ })

    expect(screen.queryByTestId("history-result")).not.toBeInTheDocument()

    await userEvent.click(entry)

    await waitFor(() => {
      expect(screen.getByTestId("history-result")).toBeInTheDocument()
    })
    expect(screen.getByTestId("summary")).toHaveTextContent(
      "Praca spełnia wymagania",
    )
    expect(screen.queryByTestId("recommendation")).not.toBeInTheDocument()
  })

  it("closes it again on a second click", async () => {
    renderDetail()
    await openHistorySection()
    const entry = await screen.findByRole("button", { name: /Recenzja/ })

    await userEvent.click(entry)
    await waitFor(() => {
      expect(screen.getByTestId("history-result")).toBeInTheDocument()
    })
    await userEvent.click(entry)

    await waitFor(() => {
      expect(screen.queryByTestId("history-result")).not.toBeInTheDocument()
    })
  })

  it("offers the way back to a running action on the overview", async () => {
    const pending = { ...REVIEW, id: "a2", status: "running", output: null }
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              url.endsWith("/actions")
                ? [pending]
                : url.endsWith("/meeting-notes") ||
                    url.endsWith("/drafts") ||
                    url.includes("/guidelines/")
                  ? []
                  : STUDENT,
            ),
            { status: 200 },
          ),
        ),
      ),
    )
    renderDetail()

    const banner = await screen.findByTestId("unfinished-banner")
    expect(banner).toHaveTextContent("Akcja w toku")
    await userEvent.click(screen.getByRole("button", { name: "Pokaż postęp" }))

    expect(await screen.findByRole("heading", { name: "Akcje AI" })).toBeInTheDocument()
  })

  it("leads from an action still running to where its progress is shown", async () => {
    const pending = { ...REVIEW, id: "a2", status: "running", output: null }
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              url.endsWith("/actions")
                ? [pending]
                : url.endsWith("/meeting-notes") ||
                    url.endsWith("/drafts") ||
                    url.includes("/guidelines/")
                  ? []
                  : STUDENT,
            ),
            { status: 200 },
          ),
        ),
      ),
    )
    renderDetail()
    await openHistorySection()

    const entry = await screen.findByRole("button", { name: /Recenzja/ })
    // Nothing to unfold yet — it is the way back to the running action.
    await userEvent.click(entry)

    expect(await screen.findByRole("heading", { name: "Akcje AI" })).toBeInTheDocument()
    expect(screen.queryByTestId("history-result")).not.toBeInTheDocument()
  })

  it("deletes an action from the history after asking", async () => {
    let actions = [REVIEW]
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "DELETE") {
        actions = []
        return Promise.resolve(new Response(null, { status: 204 }))
      }
      const body = url.endsWith("/actions")
        ? actions
        : url.endsWith("/meeting-notes") ||
            url.endsWith("/drafts") ||
            url.includes("/guidelines/")
          ? []
          : STUDENT
      return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
    })
    vi.stubGlobal("fetch", fetchMock)
    renderDetail()
    await openHistorySection()

    await userEvent.click(await screen.findByRole("button", { name: "Usuń z historii" }))
    await userEvent.click(screen.getByRole("button", { name: "Usuń" }))

    expect(await screen.findByText("Nic jeszcze nie uruchomiono.")).toBeInTheDocument()
    const del = fetchMock.mock.calls.find(([, init]) => init?.method === "DELETE")
    expect(del?.[0]).toBe("/api/students/s1/actions/a1")
  })
})
