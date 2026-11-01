import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import StudentDetailsCard from "../students/StudentDetailsCard"
import type { Student } from "@/lib/api.types"

const STUDENT = {
  id: "s1",
  full_name: "Jan Kowalski",
  field_of_study: "Ekonomia",
  index_number: null,
  thesis_type: "bachelor",
  guideline_set_id: null,
  research_area: "ekonomia instytucjonalna",
  research_aim: null,
} as Student

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("StudentDetailsCard", () => {
  it("shows what was agreed, and a dash for what was not", () => {
    render(<StudentDetailsCard student={STUDENT} onChange={() => undefined} />)

    expect(screen.getByText("ekonomia instytucjonalna")).toBeInTheDocument()
    expect(screen.getByText("Cel i hipotezy").nextSibling).toHaveTextContent("—")
  })

  it("sends a filled aim and clears an emptied area", async () => {
    const fetchMock = vi.fn(
      async (_url: string, init?: RequestInit) =>
        new Response(init?.body as string, { status: 200 }),
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<StudentDetailsCard student={STUDENT} onChange={() => undefined} />)

    await user.click(screen.getByRole("button", { name: "Edytuj" }))
    await user.clear(screen.getByLabelText("Obszar badawczy (opcjonalnie)"))
    await user.type(screen.getByLabelText("Cel i hipotezy (opcjonalnie)", { exact: false }), "Cel: X")
    await user.click(screen.getByRole("button", { name: "Zapisz" }))

    const body = JSON.parse(fetchMock.mock.calls[0][1]?.body as string) as Record<string, unknown>
    expect(body.research_area).toBeNull()
    expect(body.research_aim).toBe("Cel: X")
  })
})
