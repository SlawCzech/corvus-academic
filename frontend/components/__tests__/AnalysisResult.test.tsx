import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import AnalysisResultView from "../AnalysisResult"
import type { ActionResult } from "@/lib/api.types"

const baseResult: ActionResult = {
  findings: [],
  scores: [],
  summary: null,
  recommendation: null,
  status: "done",
  error: null,
}

describe("AnalysisResultView", () => {
  it("renders without crashing when findings and scores are empty", () => {
    render(<AnalysisResultView result={baseResult} />)
    expect(screen.getByTestId("analysis-result")).toBeInTheDocument()
  })

  it("renders summary and recommendation when present", () => {
    const result: ActionResult = {
      ...baseResult,
      summary: "The thesis is well-structured.",
      recommendation: "Accept with minor revisions.",
    }
    render(<AnalysisResultView result={result} />)
    expect(screen.getByTestId("summary")).toHaveTextContent(
      "The thesis is well-structured.",
    )
    expect(screen.getByTestId("recommendation")).toHaveTextContent(
      "Accept with minor revisions.",
    )
  })

  it("renders findings grouped by severity", () => {
    const result: ActionResult = {
      ...baseResult,
      findings: [
        {
          section: "Introduction",
          description: "Missing research gap",
          severity: "critical",
          suggestion: "Add a research gap analysis.",
        },
        {
          section: "Methodology",
          description: "Weak statistical analysis",
          severity: "major",
          suggestion: "Use regression analysis.",
        },
        {
          section: "Conclusion",
          description: "Minor formatting issues",
          severity: "minor",
          suggestion: "Fix spacing.",
        },
      ],
    }
    render(<AnalysisResultView result={result} />)

    expect(screen.getByTestId("finding-group-critical")).toBeInTheDocument()
    expect(screen.getByTestId("finding-group-major")).toBeInTheDocument()
    expect(screen.getByTestId("finding-group-minor")).toBeInTheDocument()

    const items = screen.getAllByTestId("finding-item")
    expect(items).toHaveLength(3)
  })

  it("labels each finding with the analysis that raised it", () => {
    const result: ActionResult = {
      ...baseResult,
      findings: [
        {
          section: "Wnioski",
          description: "Brak wniosków",
          severity: "critical",
          suggestion: "Dodaj wnioski.",
          source: "requirements",
        },
        {
          section: "Wstęp",
          description: "Wynik sprzed 2026-09-24, bez źródła",
          severity: "minor",
          suggestion: "",
        },
      ],
    }
    render(<AnalysisResultView result={result} />)

    const labels = screen.getAllByTestId("finding-source")
    expect(labels).toHaveLength(1)
    expect(labels[0]).toHaveTextContent("Wymogi")
  })

  it("shows the passage a finding rests on, and nothing for an absence", () => {
    const result: ActionResult = {
      ...baseResult,
      findings: [
        {
          section: "3.1",
          description: "Próba nieopisana",
          severity: "major",
          suggestion: "Opisać próbę.",
          quote: "przeprowadzono ankietę wśród znajomych autora",
        },
        {
          section: "Wstęp",
          description: "Brak hipotez",
          severity: "critical",
          suggestion: "Dodać hipotezy.",
          quote: "",
        },
      ],
    }
    render(<AnalysisResultView result={result} />)
    const quotes = screen.getAllByTestId("finding-quote")
    expect(quotes).toHaveLength(1)
    expect(quotes[0]).toHaveTextContent("przeprowadzono ankietę wśród znajomych autora")
  })

  it("hides severity groups that have no findings", () => {
    const result: ActionResult = {
      ...baseResult,
      findings: [
        {
          section: "Abstract",
          description: "Too short",
          severity: "minor",
          suggestion: "Expand to 200 words.",
        },
      ],
    }
    render(<AnalysisResultView result={result} />)

    expect(screen.queryByTestId("finding-group-critical")).not.toBeInTheDocument()
    expect(screen.queryByTestId("finding-group-major")).not.toBeInTheDocument()
    expect(screen.getByTestId("finding-group-minor")).toBeInTheDocument()
  })

  it("renders scores as progress bars with correct percentages", () => {
    const result: ActionResult = {
      ...baseResult,
      scores: [
        { criteria: "Structure", points: 8, max_points: 10 },
        { criteria: "Methodology", points: 6, max_points: 10 },
      ],
    }
    render(<AnalysisResultView result={result} />)

    const bars = screen.getAllByRole("progressbar")
    expect(bars).toHaveLength(2)
    expect(bars[0]).toHaveAttribute("aria-valuenow", "80")
    expect(bars[1]).toHaveAttribute("aria-valuenow", "60")
  })

  it("handles zero max_points gracefully", () => {
    const result: ActionResult = {
      ...baseResult,
      scores: [{ criteria: "N/A", points: 0, max_points: 0 }],
    }
    render(<AnalysisResultView result={result} />)

    const [bar] = screen.getAllByRole("progressbar")
    expect(bar).toHaveAttribute("aria-valuenow", "0")
  })

  it("does not render findings section when list is empty", () => {
    render(<AnalysisResultView result={baseResult} />)
    expect(screen.queryByTestId("finding-item")).not.toBeInTheDocument()
  })
})
