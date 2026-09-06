import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import ActionResultView from "../students/ActionResultView"
import type { AgentAction } from "@/lib/api.types"

const base: AgentAction = {
  id: "a1",
  student_id: "s1",
  promotor_id: "p1",
  action_type: "propose_topic",
  status: "completed",
  task_id: "t1",
  detail: null,
  output: null,
  error: null,
  accepted: false,
  accepted_at: null,
  created_at: "2026-03-01T10:00:00Z",
  updated_at: "2026-03-01T10:00:00Z",
}

describe("ActionResultView", () => {
  it("lists proposed topics as choices", () => {
    const action: AgentAction = {
      ...base,
      output: {
        output: {
          topics: [
            { title: "Instytucje a wzrost", rationale: "luka badawcza" },
            { title: "Kapitał społeczny" },
          ],
        },
      },
    }
    render(<ActionResultView action={action} selected={0} onSelect={vi.fn()} />)

    expect(screen.getByTestId("topics")).toBeInTheDocument()
    expect(screen.getByText("Instytucje a wzrost")).toBeInTheDocument()
    expect(screen.getByText("Kapitał społeczny")).toBeInTheDocument()
  })

  it("numbers the defence questions", () => {
    const action: AgentAction = {
      ...base,
      action_type: "defence_questions",
      output: {
        output: {
          questions: [
            { question: "Dlaczego ta metoda?", rationale: "sprawdza metodę" },
          ],
        },
      },
    }
    render(<ActionResultView action={action} selected={0} onSelect={vi.fn()} />)

    expect(screen.getByTestId("questions")).toBeInTheDocument()
    expect(screen.getByText("1. Dlaczego ta metoda?")).toBeInTheDocument()
  })

  it("shows the drafted note ready to be saved", () => {
    const action: AgentAction = {
      ...base,
      action_type: "draft_meeting_note",
      output: { output: { content: "Omówiliśmy rozdział 2." } },
    }
    render(<ActionResultView action={action} selected={0} onSelect={vi.fn()} />)

    expect(screen.getByTestId("drafted-note")).toHaveTextContent(
      "Omówiliśmy rozdział 2.",
    )
  })

  it("shows the error instead of a result when the action failed", () => {
    const action: AgentAction = {
      ...base,
      status: "failed",
      error: "Ollama unreachable",
    }
    render(<ActionResultView action={action} selected={0} onSelect={vi.fn()} />)

    expect(screen.getByTestId("action-error")).toHaveTextContent(
      "Ollama unreachable",
    )
  })

  it("falls back to the review renderer for findings-based actions", () => {
    const action: AgentAction = {
      ...base,
      action_type: "generate_review",
      output: {
        findings: [],
        scores: [],
        summary: "Praca spełnia wymogi.",
        recommendation: "Dopuścić do obrony",
      },
    }
    render(<ActionResultView action={action} selected={0} onSelect={vi.fn()} />)

    expect(screen.getByTestId("summary")).toHaveTextContent(
      "Praca spełnia wymogi.",
    )
  })
})
