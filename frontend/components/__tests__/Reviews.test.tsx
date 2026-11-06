import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { SWRConfig } from "swr"
import ReviewDetail from "../reviews/ReviewDetail"
import ReviewList from "../reviews/ReviewList"
import StudentDetail from "../students/StudentDetail"

const mockPush = vi.fn()
const mockReplace = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
}))

const REVIEW = {
  id: "r1",
  full_name: "Anna Nowak",
  field_of_study: "Ekonomia",
  thesis_type: "bachelor",
  current_topic: null,
  created_at: "2026-11-01T10:00:00Z",
  filename: "praca.docx",
  purged_at: null,
  purge_due_at: "2027-03-31T10:00:00Z",
}

const STUDENT = {
  id: "r1",
  promotor_id: "p1",
  full_name: "Anna Nowak",
  field_of_study: "Ekonomia",
  thesis_type: "bachelor",
  current_topic: null,
  current_topic_set_at: null,
  research_area: null,
  research_aim: null,
  status: "archived",
  created_at: "2026-11-01T10:00:00Z",
  updated_at: "2026-11-01T10:00:00Z",
  closed_at: "2026-11-01T10:00:00Z",
  guideline_set_id: null,
  is_one_off: true,
}

const THESIS = {
  id: "d1",
  filename: "praca.docx",
  has_file: true,
  purged_at: null,
  purge_due_at: "2027-03-31T10:00:00Z",
}

const SET = {
  id: "set1",
  name: "Prace licencjackie",
  thesis_type: "bachelor",
  university: { id: "u1", name: "Uniwersytet Ekonomiczny w Katowicach", short_name: "UE Katowice" },
  current: { id: "v1", version_no: 1 },
  has_draft: false,
}

const NOTHING_FOUND = {
  full_name: null,
  field_of_study: null,
  thesis_type: null,
  current_topic: null,
}

function json(body: unknown, status = 200): Promise<Response> {
  return Promise.resolve(new Response(JSON.stringify(body), { status }))
}

function fresh(ui: React.ReactElement): void {
  render(<SWRConfig value={{ provider: () => new Map() }}>{ui}</SWRConfig>)
}

describe("one-off reviews", () => {
  const fetchMock = vi.fn()
  let student: typeof STUDENT
  let titlePage: () => Promise<Response>
  let thesis: Omit<typeof THESIS, "purged_at"> & { purged_at: string | null }

  beforeEach(() => {
    student = STUDENT
    titlePage = () => json(NOTHING_FOUND)
    thesis = THESIS
    mockPush.mockReset()
    mockReplace.mockReset()
    fetchMock.mockReset()
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url === "/api/reviews/title-page") return titlePage()
      if (url.startsWith("/api/guidelines/sets")) return json([SET])
      if (url === "/api/reviews" && init?.method === "POST") return json(REVIEW, 201)
      if (url === "/api/reviews") return json([REVIEW])
      if (url === "/api/reviews/r1/promote") return json({ ...STUDENT, is_one_off: false })
      if (url === "/api/students/r1") return json(student)
      if (url.endsWith("/drafts")) return json([thesis])
      if (url.endsWith("/actions")) return json([])
      if (url.endsWith("/meeting-notes")) return json([])
      if (url.includes("/models")) return json({ local_enabled: false, models: [] })
      return json({})
    })
    vi.stubGlobal("fetch", fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("lists a review with what happens to its thesis", async () => {
    fresh(<ReviewList />)

    expect(await screen.findByText("Anna Nowak")).toBeInTheDocument()
    expect(screen.getByText("praca.docx")).toBeInTheDocument()
    expect(screen.getByText(/Tekst pracy do/)).toBeInTheDocument()
  })

  it("sends the form with the file and opens the review", async () => {
    const { container } = render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <ReviewList />
      </SWRConfig>,
    )

    await userEvent.click(screen.getByRole("button", { name: "Nowa recenzja" }))
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(
      input,
      new File(["x"], "praca.pdf", { type: "application/pdf" }),
    )
    await userEvent.type(screen.getByLabelText("Autor pracy"), "Anna Nowak")
    await userEvent.type(screen.getByLabelText("Kierunek"), "Ekonomia")
    await chooseGuidelines()
    await userEvent.click(screen.getByRole("button", { name: "Dalej" }))

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/reviews/r1"))
    const post = fetchMock.mock.calls.find(
      ([url, init]) => url === "/api/reviews" && init?.method === "POST",
    )
    const form = post?.[1]?.body as FormData
    expect(form.get("full_name")).toBe("Anna Nowak")
    expect(form.get("thesis_type")).toBe("bachelor")
    expect(form.get("file")).toBeInstanceOf(File)
    expect(form.get("guideline_set_id")).toBe("set1")
    expect(form.has("current_topic")).toBe(false)
  })

  async function chooseGuidelines(): Promise<void> {
    const select = screen.getByRole("combobox", { name: "Zestaw wytycznych" })
    await waitFor(() => expect(select).toBeEnabled())
    await userEvent.selectOptions(select, "set1")
  }

  async function chooseThesis(container: HTMLElement): Promise<void> {
    await userEvent.click(screen.getByRole("button", { name: "Nowa recenzja" }))
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, new File(["x"], "praca.pdf", { type: "application/pdf" }))
  }

  function renderForm(): HTMLElement {
    return render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <ReviewList />
      </SWRConfig>,
    ).container
  }

  it("fills the form from the title page and asks to check it", async () => {
    titlePage = () =>
      json({
        full_name: "Anna Nowak",
        field_of_study: "Ekonomia",
        thesis_type: "master_article",
        current_topic: "Instytucje a handel",
      })

    await chooseThesis(renderForm())

    expect(await screen.findByTestId("title-page-note")).toBeInTheDocument()
    expect(screen.getByLabelText("Autor pracy")).toHaveValue("Anna Nowak")
    expect(screen.getByLabelText("Kierunek")).toHaveValue("Ekonomia")
    expect(screen.getByLabelText("Typ pracy")).toHaveValue("master_article")
    expect(screen.getByLabelText("Tytuł (opcjonalnie)")).toHaveValue("Instytucje a handel")
  })

  it("does not overwrite what the promoter already typed", async () => {
    titlePage = () => json({ ...NOTHING_FOUND, full_name: "Inna Osoba", thesis_type: "bachelor" })
    const container = renderForm()

    await userEvent.click(screen.getByRole("button", { name: "Nowa recenzja" }))
    await userEvent.type(screen.getByLabelText("Autor pracy"), "Anna Nowak")
    await userEvent.selectOptions(screen.getByLabelText("Typ pracy"), "master_article")
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, new File(["x"], "praca.pdf", { type: "application/pdf" }))

    await screen.findByTestId("title-page-note")
    expect(screen.getByLabelText("Autor pracy")).toHaveValue("Anna Nowak")
    expect(screen.getByLabelText("Typ pracy")).toHaveValue("master_article")
  })

  it("stays quiet when the title page gives nothing or cannot be read", async () => {
    titlePage = () => json({ detail: "nope" }, 422)

    await chooseThesis(renderForm())

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith("/api/reviews/title-page", expect.anything()),
    )
    expect(screen.queryByTestId("title-page-note")).not.toBeInTheDocument()
    expect(screen.getByLabelText("Autor pracy")).toHaveValue("")
  })

  it("does not send a form without a file", async () => {
    fresh(<ReviewList />)

    await userEvent.click(screen.getByRole("button", { name: "Nowa recenzja" }))
    await userEvent.type(screen.getByLabelText("Autor pracy"), "Anna Nowak")
    await userEvent.type(screen.getByLabelText("Kierunek"), "Ekonomia")
    await chooseGuidelines()
    await userEvent.click(screen.getByRole("button", { name: "Dalej" }))

    expect(await screen.findByTestId("review-form-error")).toHaveTextContent("Wybierz plik")
  })

  it("does not send a form without the university's guidelines", async () => {
    const container = renderForm()

    await chooseThesis(container)
    await userEvent.type(screen.getByLabelText("Autor pracy"), "Anna Nowak")
    await userEvent.type(screen.getByLabelText("Kierunek"), "Ekonomia")
    await userEvent.click(screen.getByRole("button", { name: "Dalej" }))

    expect(screen.getByRole("combobox", { name: "Zestaw wytycznych" })).toBeInvalid()
    expect(
      fetchMock.mock.calls.some(([url, init]) => url === "/api/reviews" && init?.method === "POST"),
    ).toBe(false)
  })

  it("offers only what a reviewer needs", async () => {
    fresh(<ReviewDetail reviewId="r1" />)

    expect(await screen.findByRole("button", { name: "Recenzja finalna" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Sprawdź bibliografię" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Pytania na obronę" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Recenzja próbna" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Zaproponuj temat" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Spisz notatkę" })).not.toBeInTheDocument()
  })

  it("promotes only after a second click, then moves to the student", async () => {
    fresh(<ReviewDetail reviewId="r1" />)

    await userEvent.click(await screen.findByTestId("promote-review"))
    expect(fetchMock).not.toHaveBeenCalledWith(
      "/api/reviews/r1/promote",
      expect.anything(),
    )
    await userEvent.click(screen.getByTestId("promote-confirm"))

    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/students/r1"))
  })

  it("says a purged thesis stops the actions and what promotion still brings", async () => {
    thesis = { ...THESIS, has_file: false, purged_at: "2027-04-01T10:00:00Z" }
    fresh(<ReviewDetail reviewId="r1" />)

    expect(await screen.findByTestId("promote-purged")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Recenzja finalna" })).not.toBeInTheDocument()
    expect(screen.getByText(/Tekst pracy został usunięty/)).toBeInTheDocument()
  })

  it("sends a promoted review to the student page", async () => {
    student = { ...STUDENT, is_one_off: false }
    fresh(<ReviewDetail reviewId="r1" />)

    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/students/r1"))
  })

  it("sends a link from the dashboard on to the review's own page", async () => {
    fresh(<StudentDetail studentId="r1" />)

    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/reviews/r1"))
  })
})
