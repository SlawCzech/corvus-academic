import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { SWRConfig } from "swr"
import GuidelineVersionView from "../guidelines/GuidelineVersionView"
import GuidelineDraftEditor from "../guidelines/GuidelineDraftEditor"
import GuidelinePicker from "../students/GuidelinePicker"
import type { GuidelineSet, GuidelineVersion, Student } from "@/lib/api.types"

const UE = { id: "u1", name: "Uniwersytet Ekonomiczny w Katowicach", short_name: "UE Katowice" }

const VERSION: GuidelineVersion = {
  id: "v2",
  set_id: "set1",
  set_name: "Prace licencjackie",
  thesis_type: "bachelor",
  university: UE,
  version_no: 2,
  status: "published",
  effective_from: "2026-10-01",
  published_at: "2026-09-20T10:00:00Z",
  created_at: "2026-09-19T10:00:00Z",
  rubric_md: "## 2.2 Bibliography\n- Minimum 25 sources",
  thresholds: {
    min_sources: 25,
    min_foreign_sources: 4,
    min_body_chars: null,
    max_body_chars: null,
  },
  source: { filename: "Zarządzenie 117-22.pdf", sha256: "abc", size: 1000, downloadable: true },
  created_by: "a1",
  published_by: "a1",
}

const SET: GuidelineSet = {
  id: "set1",
  name: "Prace licencjackie",
  thesis_type: "bachelor",
  university: UE,
  current: VERSION,
  has_draft: false,
}

const STUDENT = {
  id: "s1",
  thesis_type: "bachelor",
  guideline_set_id: null,
} as unknown as Student

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status })
}

function withSWR(ui: React.ReactNode) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>{ui}</SWRConfig>,
  )
}

describe("guideline catalog UI", () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock)
    fetchMock.mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("shows a version's numbers, rubric, original and history", async () => {
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve(
        url.includes("/sets/")
          ? json({
              ...SET,
              versions: [VERSION, { ...VERSION, id: "v1", version_no: 1, status: "superseded" }],
            })
          : json(VERSION),
      ),
    )

    withSWR(<GuidelineVersionView versionId="v2" />)

    expect(await screen.findByTestId("rubric")).toHaveTextContent("Minimum 25 sources")
    expect(screen.getByText("Minimalna liczba źródeł").nextSibling).toHaveTextContent("25")
    expect(screen.queryByText(/Objętość pracy/)).not.toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Pobierz oryginał" })).toHaveAttribute(
      "href",
      "/api/guidelines/versions/v2/source",
    )
    expect(await screen.findByRole("link", { name: "Wersja 1" })).toHaveAttribute(
      "href",
      "/guidelines/v1",
    )
  })

  it("offers only sets with a version in force, and saves the choice", async () => {
    const draftOnly = { ...SET, id: "set2", name: "Szkic", current: null }
    fetchMock.mockImplementation((url: string, init?: RequestInit) =>
      Promise.resolve(
        init?.method === "PATCH"
          ? json({ ...STUDENT, guideline_set_id: "set1" })
          : json([SET, draftOnly]),
      ),
    )
    const onChange = vi.fn()

    withSWR(<GuidelinePicker student={STUDENT} onChange={onChange} />)

    const select = await screen.findByRole("combobox", { name: "Zestaw wytycznych" })
    await waitFor(() => expect(screen.getAllByRole("option")).toHaveLength(2))
    expect(fetchMock.mock.calls[0][0]).toBe("/api/guidelines/sets?thesis_type=bachelor")

    await userEvent.selectOptions(select, "set1")

    await waitFor(() => expect(onChange).toHaveBeenCalled())
    const patch = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH")
    expect(JSON.parse(patch![1].body as string)).toEqual({ guideline_set_id: "set1" })
  })

  it("warns that the built-in requirements are not the university's", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(json([SET])))

    withSWR(<GuidelinePicker student={STUDENT} onChange={vi.fn()} />)

    expect(await screen.findByTestId("default-guidelines")).toHaveTextContent(
      "nie wytyczne Twojej uczelni",
    )
  })

  it("does not warn once a university's set is chosen", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(json([SET])))

    withSWR(
      <GuidelinePicker student={{ ...STUDENT, guideline_set_id: "set1" }} onChange={vi.fn()} />,
    )

    expect(await screen.findByText(/według wersji 2/)).toBeInTheDocument()
    expect(screen.queryByTestId("default-guidelines")).not.toBeInTheDocument()
  })

  it("saves the draft's thresholds as numbers, empty ones as null, then publishes", async () => {
    const draft = { ...VERSION, status: "draft" as const, published_at: null }
    fetchMock.mockImplementation((url: string, init?: RequestInit) =>
      Promise.resolve(json(init?.method ? { ...draft, status: "published" } : draft)),
    )
    const onDone = vi.fn()

    withSWR(<GuidelineDraftEditor versionId="v2" onDone={onDone} />)

    const minSources = await screen.findByLabelText("Minimalna liczba źródeł")
    await userEvent.clear(minSources)
    await userEvent.type(minSources, "30")
    await userEvent.click(screen.getByRole("button", { name: "Opublikuj" }))

    await waitFor(() => expect(onDone).toHaveBeenCalled())
    const patch = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH")
    const body = JSON.parse(patch![1].body as string)
    expect(body.thresholds).toEqual({
      min_sources: 30,
      min_foreign_sources: 4,
      min_body_chars: null,
      max_body_chars: null,
    })
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          url === "/api/admin/guidelines/versions/v2/publish" && init?.method === "POST",
      ),
    ).toBe(true)
  })
})
