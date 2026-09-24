import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import LatestResults, { latestResults } from "../students/LatestResults"
import type { AgentAction } from "@/lib/api.types"

/**
 * The overview answers "what do we know about this student now": the newest
 * finished result of each action, readable without digging through the
 * history.
 */
function action(overrides: Partial<AgentAction>): AgentAction {
  return {
    id: "a1",
    student_id: "s1",
    promotor_id: "p1",
    action_type: "generate_review",
    status: "completed",
    task_id: "t1",
    detail: null,
    output: { summary: "Stara recenzja", scores: [], findings: [] },
    error: null,
    accepted: false,
    accepted_at: null,
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-09-01T10:00:00Z",
    ...overrides,
  }
}

// Newest first, as the API returns them.
const ACTIONS: AgentAction[] = [
  action({
    id: "q1",
    action_type: "defence_questions",
    created_at: "2026-09-20T10:00:00Z",
    output: { output: { questions: [{ question: "Dlaczego ta metoda?" }] } },
  }),
  action({
    id: "r2",
    created_at: "2026-09-12T10:00:00Z",
    output: { summary: "Nowa recenzja", scores: [], findings: [] },
  }),
  action({ id: "f1", action_type: "check_progress", status: "failed", output: null }),
  action({ id: "r1" }),
]

describe("latestResults", () => {
  it("keeps the newest finished result of each type, review first", () => {
    const latest = latestResults(ACTIONS)
    expect(latest.map((l) => l.action.id)).toEqual(["r2", "q1"])
  })

  it("says when a newer run of the same action is still going", () => {
    const running = action({
      id: "r3",
      status: "running",
      output: null,
      created_at: "2026-09-24T10:00:00Z",
    })
    const [review] = latestResults([running, ...ACTIONS])
    expect(review?.action.id).toBe("r2")
    expect(review?.newerRunning).toBe(true)
  })
})

describe("LatestResults", () => {
  it("opens the review in place", async () => {
    render(<LatestResults actions={ACTIONS} onShowHistory={vi.fn()} />)
    const card = screen.getByTestId("latest-results")

    await userEvent.click(within(card).getByRole("button", { name: /Recenzja/ }))

    expect(screen.getByTestId("latest-result")).toHaveTextContent("Nowa recenzja")
  })

  it("opens the defence questions in place", async () => {
    render(<LatestResults actions={ACTIONS} onShowHistory={vi.fn()} />)

    await userEvent.click(screen.getByRole("button", { name: /Pytania na obronę/ }))

    expect(screen.getByTestId("latest-result")).toHaveTextContent("1. Dlaczego ta metoda?")
  })

  it("says there is nothing yet", () => {
    render(<LatestResults actions={[]} onShowHistory={vi.fn()} />)
    expect(screen.getByTestId("latest-results")).toHaveTextContent("Nie ma jeszcze żadnych wyników")
  })

  it("leads to the full history", async () => {
    const onShowHistory = vi.fn()
    render(<LatestResults actions={ACTIONS} onShowHistory={onShowHistory} />)

    await userEvent.click(screen.getByRole("button", { name: /Cała historia/ }))

    expect(onShowHistory).toHaveBeenCalled()
  })
})
