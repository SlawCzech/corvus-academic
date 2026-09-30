import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import ActionProgress from "../students/ActionProgress"

describe("ActionProgress", () => {
  it("ticks off the steps the agent finished, in the agent's order", () => {
    render(
      <ActionProgress
        progress={{
          steps: ["analyze_structure", "analyze_methodology", "verify", "generate_review"],
          done: ["analyze_methodology"],
        }}
      />,
    )
    const steps = screen.getAllByTestId("progress-step")
    expect(steps.map((s) => s.textContent)).toEqual([
      "Struktura i spójność",
      "Metodologia i źródła",
      "Weryfikacja uwag",
      "Recenzja",
    ])
    expect(steps.map((s) => s.dataset.done)).toEqual(["false", "true", "false", "false"])
  })

  it("shows a step it has no label for under the agent's own name", () => {
    render(<ActionProgress progress={{ steps: ["new_node"], done: [] }} />)
    expect(screen.getByTestId("progress-step")).toHaveTextContent("new_node")
  })
})
