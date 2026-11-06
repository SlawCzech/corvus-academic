import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { SWRConfig } from "swr"
import StudentDetail from "../students/StudentDetail"

const mockPush = vi.fn()
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}))

/**
 * Not everything about a student has to come from the AI: the promoter types
 * the topic agreed in person and corrects the student's details by hand, on
 * the overview — which is where the page opens.
 */
const STUDENT = {
  id: "s1",
  promotor_id: "p1",
  full_name: "Julia Krzemień",
  field_of_study: "Zarządzanie",
  thesis_type: "master_article",
  current_topic: null,
  current_topic_set_at: null,
  research_area: null,
  research_aim: null,
  status: "active",
  created_at: "2026-03-01T10:00:00Z",
  updated_at: "2026-03-01T10:00:00Z",
  closed_at: null,
  guideline_set_id: "set1",
}

const SET = {
  id: "set1",
  name: "Prace magisterskie",
  thesis_type: "master_article",
  university: { id: "u1", name: "UE Katowice", short_name: "UE Katowice" },
  current: { id: "v1", version_no: 1 },
  has_draft: false,
}

type Call = {
  url: string
  method: string
  body: Record<string, unknown> | null
}
let calls: Call[] = []
let student: Record<string, unknown>

function json(body: unknown): Promise<Response> {
  return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
}

function renderDetail(): void {
  render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <StudentDetail studentId="s1" />
    </SWRConfig>,
  )
}

function patches(): Record<string, unknown>[] {
  return calls.filter((c) => c.method === "PATCH").map((c) => c.body ?? {})
}

describe("StudentDetail — overview", () => {
  beforeEach(() => {
    calls = []
    student = { ...STUDENT }
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET"
        const body = init?.body
          ? (JSON.parse(init.body as string) as Record<string, unknown>)
          : null
        calls.push({ url, method, body })
        if (method === "DELETE") return Promise.resolve(new Response(null, { status: 204 }))
        if (method === "PATCH" && body) {
          student = {
            ...student,
            ...body,
            ...("current_topic" in body
              ? {
                  current_topic_set_at: body.current_topic ? "2026-09-24T10:00:00Z" : null,
                  research_area: null,
                  research_aim: null,
                }
              : {}),
          }
          return json(student)
        }
        if (url.endsWith("/actions") || url.endsWith("/meeting-notes") || url.endsWith("/drafts"))
          return json([])
        if (url.includes("/guidelines/sets")) return json([SET])
        if (url.includes("/guidelines/")) return json([])
        return json(student)
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("opens on the overview, not on the AI actions", async () => {
    renderDetail()
    expect(await screen.findByRole("heading", { name: "Przegląd" })).toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "Akcje AI" })).not.toBeInTheDocument()
  })

  it("saves a topic typed by hand", async () => {
    renderDetail()
    const card = await screen.findByTestId("topic-card")
    expect(card).toHaveTextContent("Temat nieustalony")

    await userEvent.click(within(card).getByRole("button", { name: "Wpisz temat" }))
    await userEvent.type(within(card).getByLabelText("Temat pracy"), "FOMO a zakupy impulsywne")
    await userEvent.click(within(card).getByRole("button", { name: "Zapisz temat" }))

    await waitFor(() => expect(card).toHaveTextContent("FOMO a zakupy impulsywne"))
    expect(patches()).toEqual([{ current_topic: "FOMO a zakupy impulsywne" }])
  })

  it("clears the topic with null", async () => {
    student = { ...STUDENT, current_topic: "Stary temat" }
    renderDetail()
    const card = await screen.findByTestId("topic-card")

    await userEvent.click(within(card).getByRole("button", { name: "Zmień" }))
    await userEvent.click(within(card).getByRole("button", { name: "Usuń temat" }))

    await waitFor(() => expect(card).toHaveTextContent("Temat nieustalony"))
    expect(patches()).toEqual([{ current_topic: null }])
  })

  it("offers the AI proposals when there is no topic", async () => {
    renderDetail()
    const card = await screen.findByTestId("topic-card")

    await userEvent.click(within(card).getByRole("button", { name: /poproś AI/ }))

    expect(await screen.findByRole("heading", { name: "Akcje AI" })).toBeInTheDocument()
  })

  it("edits the student's details", async () => {
    renderDetail()
    const details = await screen.findByTestId("student-details")
    await userEvent.click(within(details).getByRole("button", { name: "Edytuj" }))

    const form = screen.getByTestId("student-form")
    const name = within(form).getByLabelText("Imię i nazwisko")
    await userEvent.clear(name)
    await userEvent.type(name, "Julia Nowak")
    await waitFor(() =>
      expect(within(form).getByRole("combobox", { name: "Zestaw wytycznych" })).toHaveValue("set1"),
    )
    await userEvent.click(within(form).getByRole("button", { name: "Zapisz" }))

    await waitFor(() =>
      expect(screen.getByTestId("student-details")).toHaveTextContent("Julia Nowak"),
    )
    expect(patches()).toEqual([
      {
        full_name: "Julia Nowak",
        field_of_study: "Zarządzanie",
        thesis_type: "master_article",
        research_area: null,
        research_aim: null,
        guideline_set_id: "set1",
      },
    ])
  })

  it("deletes the student only once their name is typed", async () => {
    renderDetail()
    await userEvent.click(await screen.findByRole("button", { name: "Usuń studenta" }))
    const panel = screen.getByTestId("delete-student")
    const confirm = within(panel).getByRole("button", { name: "Usuń na zawsze" })

    expect(confirm).toBeDisabled()
    await userEvent.type(within(panel).getByRole("textbox"), "Julia Krzemień")
    await userEvent.click(confirm)

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/students"))
    expect(calls.some((c) => c.method === "DELETE" && c.url === "/api/students/s1")).toBe(true)
  })

  it("keeps the student when the AI service cannot confirm the deletion", async () => {
    mockPush.mockClear()
    const base = vi.mocked(fetch).getMockImplementation()!
    vi.mocked(fetch).mockImplementation((url, init) =>
      init?.method === "DELETE"
        ? Promise.resolve(new Response(null, { status: 503 }))
        : base(url, init),
    )
    renderDetail()
    await userEvent.click(await screen.findByRole("button", { name: "Usuń studenta" }))
    const panel = screen.getByTestId("delete-student")
    await userEvent.type(within(panel).getByRole("textbox"), "Julia Krzemień")
    await userEvent.click(within(panel).getByRole("button", { name: "Usuń na zawsze" }))

    expect(await within(panel).findByRole("alert")).toHaveTextContent("nic nie zostało usunięte")
    expect(mockPush).not.toHaveBeenCalled()
  })

  it("changes the status in one click, from any section", async () => {
    renderDetail()
    const select = await screen.findByRole("combobox", { name: "Status: Julia Krzemień" })

    await userEvent.selectOptions(select, "graduated")

    await waitFor(() => expect(patches()).toEqual([{ status: "graduated" }]))
    await waitFor(() =>
      expect(screen.getByRole("combobox", { name: "Status: Julia Krzemień" })).toHaveValue(
        "graduated",
      ),
    )
  })
})
