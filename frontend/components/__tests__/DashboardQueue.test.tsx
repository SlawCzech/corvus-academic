import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { SWRConfig } from "swr"
import { afterEach, describe, expect, it, vi } from "vitest"
import DashboardPage from "@/app/dashboard/page"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}))

function fragments(count: number) {
  return Array.from({ length: count }, (_, i) => ({
    fragment_id: `f-${i}`,
    student_id: `s-${i}`,
    student_name: `Student ${i}`,
    part_name: "Rozdział 1",
    round_number: 1,
    received_on: "2026-11-01",
  }))
}

function stubSummary(feedbackCount: number) {
  const summary = {
    active_students: feedbackCount,
    without_topic: 0,
    actions_in_progress: 0,
    awaiting_input: [],
    recent_activity: [],
    awaiting_feedback: fragments(feedbackCount),
    overdue_parts: [],
  }
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify(summary), { status: 200 }))),
  )
}

function renderPage() {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <DashboardPage />
    </SWRConfig>,
  )
}

afterEach(() => vi.unstubAllGlobals())

describe("Dashboard queue", () => {
  it("shows five fragments and folds the rest behind a button", async () => {
    stubSummary(8)
    const user = userEvent.setup()
    renderPage()
    expect(await screen.findByText("Student 0")).toBeInTheDocument()
    expect(screen.getByText("Student 4")).toBeInTheDocument()
    expect(screen.queryByText("Student 5")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Pokaż wszystkie (8)" }))
    expect(screen.getByText("Student 7")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Pokaż wszystkie/ })).not.toBeInTheDocument()
  })

  it("has no button when the queue is short", async () => {
    stubSummary(3)
    renderPage()
    expect(await screen.findByText("Student 2")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Pokaż wszystkie/ })).not.toBeInTheDocument()
  })
})
