import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import FindingPicker from "../students/FindingPicker"
import type { Finding } from "@/lib/api.types"

function finding(over: Partial<Finding>): Finding {
  return { section: "s", description: "d", severity: "minor", suggestion: "", ...over }
}

// The order the agent returns them in: whichever analysis finished first.
const FINDINGS: Finding[] = [
  finding({ section: "Przypisy", severity: "minor", source: "requirements" }),
  finding({ section: "Wnioski", severity: "critical", source: "coherence" }),
  finding({ section: "Metoda", severity: "major", source: "methodology" }),
  finding({ section: "Wstęp", severity: "critical", source: "structure" }),
  finding({ section: "Literatura", severity: "minor", source: "methodology" }),
]

function sections(): string[] {
  return screen
    .getAllByRole("listitem")
    .map((item) => within(item).getByText(/Przypisy|Wnioski|Metoda|Wstęp|Literatura/).textContent ?? "")
}

describe("FindingPicker", () => {
  it("lists the gravest first, and within a severity one analysis after another", () => {
    render(<FindingPicker findings={FINDINGS} onSubmit={vi.fn()} />)

    expect(sections()).toEqual(["Wstęp", "Wnioski", "Metoda", "Literatura", "Przypisy"])
    expect(screen.getByTestId("picker-group-critical")).toHaveTextContent("Krytyczne (2/2)")
  })

  it("sends back the indices the agent knows, not the order on screen", async () => {
    const onSubmit = vi.fn()
    render(<FindingPicker findings={FINDINGS} onSubmit={onSubmit} />)

    // First on screen is "Wstęp" — the agent's finding number 3.
    await userEvent.click(screen.getAllByTestId("finding-toggle")[0])
    await userEvent.click(screen.getByTestId("resume-action"))

    expect(onSubmit).toHaveBeenCalledWith([0, 1, 2, 4])
  })

  it("strikes a whole severity at once, and brings it back", async () => {
    const onSubmit = vi.fn()
    render(<FindingPicker findings={FINDINGS} onSubmit={onSubmit} />)

    await userEvent.click(screen.getByTestId("picker-group-toggle-minor"))
    expect(screen.getByTestId("picker-group-minor")).toHaveTextContent("Drobne (0/2)")
    await userEvent.click(screen.getByTestId("resume-action"))
    expect(onSubmit).toHaveBeenLastCalledWith([1, 2, 3])

    await userEvent.click(screen.getByTestId("picker-group-toggle-minor"))
    await userEvent.click(screen.getByTestId("resume-action"))
    expect(onSubmit).toHaveBeenLastCalledWith([0, 1, 2, 3, 4])
  })
})
