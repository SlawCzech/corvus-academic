import { render, screen, waitFor, within } from "@testing-library/react"
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
    field_of_study: "Ekonomia",
    thesis_type: "bachelor",
    current_topic: topic,
    current_topic_set_at: null,
    research_area: null,
    research_aim: null,
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

  describe("acting on a row", () => {
    let roster: ReturnType<typeof student>[]
    const fetchMock = vi.fn()

    beforeEach(() => {
      roster = STUDENTS.map((s) => ({ ...s }))
      fetchMock.mockReset()
      fetchMock.mockImplementation((url: string, init?: RequestInit) => {
        const id = url.split("/")[3]
        if (init?.method === "PATCH") {
          const changes = JSON.parse(init.body as string) as Record<string, unknown>
          const updated = { ...roster.find((s) => s.id === id)!, ...changes }
          roster = roster.map((s) => (s.id === id ? updated : s))
          return Promise.resolve(new Response(JSON.stringify(updated), { status: 200 }))
        }
        if (init?.method === "DELETE") {
          roster = roster.filter((s) => s.id !== id)
          return Promise.resolve(new Response(null, { status: 204 }))
        }
        return Promise.resolve(new Response(JSON.stringify(roster), { status: 200 }))
      })
      vi.stubGlobal("fetch", fetchMock)
    })

    it("changes a student's status right in the table", async () => {
      renderList("status=all")

      await userEvent.selectOptions(
        await screen.findByRole("combobox", { name: "Status: Anna Aktywna" }),
        "archived",
      )

      await waitFor(() =>
        expect(screen.getByRole("combobox", { name: "Status: Anna Aktywna" })).toHaveValue(
          "archived",
        ),
      )
      const patch = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH")
      expect(patch?.[0]).toBe("/api/students/s1")
      expect(JSON.parse(patch?.[1].body as string)).toEqual({ status: "archived" })
    })

    it("deletes a student from the table once their name is typed", async () => {
      renderList()

      await userEvent.click(await screen.findByRole("button", { name: "Usuń: Bartek Beztematu" }))
      const dialog = screen.getByRole("dialog", { name: "Usuń: Bartek Beztematu" })
      const confirm = within(dialog).getByRole("button", { name: "Usuń na zawsze" })
      expect(confirm).toBeDisabled()
      await userEvent.type(within(dialog).getByRole("textbox"), "Bartek Beztematu")
      await userEvent.click(confirm)

      await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
      await waitFor(() => expect(screen.queryByText("Bartek Beztematu")).not.toBeInTheDocument())
      expect(screen.getByText("Anna Aktywna")).toBeInTheDocument()
      const del = fetchMock.mock.calls.find(([, init]) => init?.method === "DELETE")
      expect(del?.[0]).toBe("/api/students/s2")
    })

    it("closes the confirmation without deleting", async () => {
      renderList()

      await userEvent.click(await screen.findByRole("button", { name: "Usuń: Anna Aktywna" }))
      await userEvent.click(screen.getByRole("button", { name: "Anuluj" }))

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
      expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false)
    })
  })

  describe("an empty roster", () => {
    it("offers the demo students, and shows them once loaded", async () => {
      let roster: unknown[] = []
      const fetchMock = vi.fn((url: string, init?: RequestInit) => {
        if (url === "/api/students/demo" && init?.method === "POST") {
          roster = [STUDENTS[0]]
          return Promise.resolve(
            new Response(JSON.stringify({ created: ["Anna Aktywna"], skipped: [] }), {
              status: 201,
            }),
          )
        }
        return Promise.resolve(new Response(JSON.stringify(roster), { status: 200 }))
      })
      vi.stubGlobal("fetch", fetchMock)
      renderList()

      await userEvent.click(await screen.findByTestId("load-demo-students"))

      expect(await screen.findByText("Anna Aktywna")).toBeInTheDocument()
      expect(screen.queryByTestId("demo-students-offer")).not.toBeInTheDocument()
    })

    it("does not offer them to a promoter who has students", async () => {
      renderList()
      expect(await screen.findByText("Anna Aktywna")).toBeInTheDocument()
      expect(screen.queryByTestId("demo-students-offer")).not.toBeInTheDocument()
    })
  })
})
