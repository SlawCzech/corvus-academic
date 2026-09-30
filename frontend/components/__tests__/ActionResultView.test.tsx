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

  it("shows proposed topics to read, with nothing to pick, without onSelect", () => {
    const action: AgentAction = {
      ...base,
      output: { output: { topics: [{ title: "Instytucje a wzrost" }] } },
    }
    render(<ActionResultView action={action} />)

    expect(screen.getByText("Instytucje a wzrost")).toBeInTheDocument()
    expect(screen.queryByRole("radio")).not.toBeInTheDocument()
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

  it("tells the promoter the provider account ran out of credits", () => {
    const action: AgentAction = {
      ...base,
      status: "failed",
      error: "anthropic: Your credit balance is too low",
      error_code: "provider_no_credits",
    }
    render(<ActionResultView action={action} selected={0} onSelect={vi.fn()} />)

    expect(screen.getByTestId("action-error")).toHaveTextContent("Skończyły się środki")
    expect(screen.getByTestId("action-error-fix")).toHaveAttribute("href", "/profile")
    // The provider's own words stay, for whoever needs the detail.
    expect(screen.getByTestId("action-error-detail")).toHaveTextContent(
      "credit balance is too low",
    )
  })

  it("sends nobody to the profile for a rate limit", () => {
    const action: AgentAction = {
      ...base,
      status: "failed",
      error: "openai: Rate limit reached",
      error_code: "provider_rate_limited",
    }
    render(<ActionResultView action={action} selected={0} onSelect={vi.fn()} />)

    expect(screen.getByTestId("action-error")).toHaveTextContent("za kilka minut")
    expect(screen.queryByTestId("action-error-fix")).not.toBeInTheDocument()
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

  it("warns when the review was written without one of its analyses", () => {
    const action: AgentAction = {
      ...base,
      action_type: "generate_review",
      output: {
        findings: [],
        scores: [],
        node_errors: ["structure: Ollama timeout"],
        summary: "Praca spełnia wymogi.",
      },
    }
    render(<ActionResultView action={action} selected={0} onSelect={vi.fn()} />)

    expect(screen.getByTestId("partial-analysis")).toHaveTextContent("struktura")
    expect(screen.getByTestId("summary")).toBeInTheDocument()
  })

  it("says nothing extra when every analysis went through", () => {
    const action: AgentAction = {
      ...base,
      action_type: "generate_review",
      output: { findings: [], scores: [], node_errors: [], summary: "OK" },
    }
    render(<ActionResultView action={action} selected={0} onSelect={vi.fn()} />)

    expect(screen.queryByTestId("partial-analysis")).not.toBeInTheDocument()
  })

  it("groups the checked bibliography, suspicious entries first", () => {
    const action = {
      ...base,
      action_type: "verify_bibliography",
      status: "completed",
      output: {
        findings: [],
        scores: [],
        summary: null,
        recommendation: null,
        status: "bibliography_checked",
        error: null,
        output: {
          references: [
            { entry: "Laibson (1997). Golden eggs…", status: "verified", note: "", doi: "10.1162/x" },
            { entry: "Nowak (2019). Cryptographic…", status: "suspicious", note: "Brak w JME.", doi: "" },
            { entry: "Bankier.pl (2023)…", status: "website", note: "", doi: "" },
          ],
        },
      },
    } as unknown as AgentAction
    render(<ActionResultView action={action} />)

    const check = screen.getByTestId("bibliography-check")
    const headings = [...check.querySelectorAll("h4")].map((h) => h.textContent)
    expect(headings).toEqual(["Podejrzana (1)", "Strona www (1)", "Potwierdzona (1)"])
    expect(screen.getByTestId("references-suspicious")).toHaveTextContent("Brak w JME.")
    expect(screen.getByRole("link", { name: "doi:10.1162/x" })).toHaveAttribute(
      "href",
      "https://doi.org/10.1162/x",
    )
  })
})
