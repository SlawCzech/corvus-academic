import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { SWRConfig } from "swr"
import StudentList from "../students/StudentList"

/**
 * The roster keeps its filters in the URL so the dashboard tiles can link
 * into it ("Bez ustalonego tematu" → /students?topic=none). Default view is
 * active students only — graduated and archived ones are one tab away.
 */
const mockReplace = vi.fn()
let mockSearch = ""

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => "/students",
  useSearchParams: () => new URLSearchParams(mockSearch),
}))

function student(id: string, name: string, status: string, topic: string | null) {
  return {
    id,
    promotor_id: "p1",
    full_name: name,
    index_number: null,
    field_of_study: "Ekonomia",
    thesis_type: "bachelor",
    current_topic: topic,
    current_topic_set_at: null,
    status,
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-09-01T10:00:00Z",
    closed_at: null,
    guideline_set_id: null,
  }
}

const STUDENTS = [
  student("s1", "Anna Aktywna", "active", "Inflacja a płace"),
  student("s2", "Bartek Beztematu", "active", null),
  student("s3", "Celina Obroniona", "graduated", "Rynek pracy"),
  student("s4", "Dawid Archiwalny", "archived", null),
]

function renderList(search = ""): void {
  mockSearch = search
  render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <StudentList />
    </SWRConfig>,
  )
}

describe("StudentList", () => {
  beforeEach(() => {
    mockReplace.mockReset()
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(new Response(JSON.stringify(STUDENTS), { status: 200 })),
      ),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("shows only active students by default", async () => {
    renderList()
    expect(await screen.findByText("Anna Aktywna")).toBeInTheDocument()
    expect(screen.getByText("Bartek Beztematu")).toBeInTheDocument()
    expect(screen.queryByText("Celina Obroniona")).not.toBeInTheDocument()
    expect(screen.queryByText("Dawid Archiwalny")).not.toBeInTheDocument()
  })

  it("narrows to students without a topic when the URL asks for it", async () => {
    renderList("topic=none")
    expect(await screen.findByText("Bartek Beztematu")).toBeInTheDocument()
    expect(screen.queryByText("Anna Aktywna")).not.toBeInTheDocument()
    expect(screen.queryByText("Dawid Archiwalny")).not.toBeInTheDocument()
  })

  it("shows everyone on the Wszyscy tab", async () => {
    renderList("status=all")
    expect(await screen.findByText("Dawid Archiwalny")).toBeInTheDocument()
    expect(screen.getByText("Celina Obroniona")).toBeInTheDocument()
  })

  it("writes the chosen tab into the URL and keeps the default out of it", async () => {
    renderList("topic=none")
    await screen.findByText("Bartek Beztematu")

    await userEvent.click(screen.getByRole("tab", { name: /Obronieni/ }))
    expect(mockReplace).toHaveBeenLastCalledWith(
      "/students?topic=none&status=graduated",
      { scroll: false },
    )

    await userEvent.click(screen.getByRole("button", { name: /Bez ustalonego tematu/ }))
    expect(mockReplace).toHaveBeenLastCalledWith("/students", { scroll: false })
  })
})
