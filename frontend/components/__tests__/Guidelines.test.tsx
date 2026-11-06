import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { SWRConfig } from "swr"
import GuidelineVersionView from "../guidelines/GuidelineVersionView"
import GuidelineAdmin from "../guidelines/GuidelineAdmin"
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

  it("shows a rubric by section, with what reads each and Corvus's weights apart", async () => {
    const rubric = [
      "# Wymogi",
      "> Źródło: zarządzenie.",
      "## Elementy pracy",
      "### Wstęp",
      "- cel pracy i",
      "  pytania badawcze",
      "## Wymogi formalne",
      "- objętość **sugerowana**",
      "## Co praca ma wykazać",
      "- logiczny tok wywodu",
      "## Waga uchybień",
      "### CRITICAL",
      "- brak wstępu",
    ].join("\n")
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve(
        url.includes("/sets/")
          ? json({ ...SET, versions: [VERSION] })
          : json({ ...VERSION, rubric_md: rubric }),
      ),
    )

    withSWR(<GuidelineVersionView versionId="v2" />)

    const elements = await screen.findByTestId("rubric-elements")
    expect(within(elements).getByRole("heading", { name: "Wstęp" })).toBeInTheDocument()
    expect(within(elements).getByText("cel pracy i pytania badawcze")).toBeInTheDocument()
    expect(within(elements).getByText(/Czyta: recenzja/)).toBeInTheDocument()
    expect(screen.getByText("sugerowana").tagName).toBe("STRONG")
    expect(within(screen.getByTestId("rubric-severity")).getByText("Jak Corvus waży uchybienia"))
      .toBeInTheDocument()
    expect(screen.getByText("Źródło: zarządzenie.")).toBeInTheDocument()
    expect(screen.queryByText("Wymogi")).not.toBeInTheDocument()
    expect(screen.queryByText(/##/)).not.toBeInTheDocument()
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

  it("asks for a university's set when none is chosen, and offers no default", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(json([SET])))

    withSWR(<GuidelinePicker student={STUDENT} onChange={vi.fn()} />)

    expect(await screen.findByTestId("missing-guidelines")).toHaveTextContent(
      "Corvus nie ma własnych wymogów",
    )
    expect(screen.queryByRole("option", { name: /Domyślne/ })).not.toBeInTheDocument()
  })

  it("does not warn once a university's set is chosen", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(json([SET])))

    withSWR(
      <GuidelinePicker student={{ ...STUDENT, guideline_set_id: "set1" }} onChange={vi.fn()} />,
    )

    expect(await screen.findByText(/według wersji 2/)).toBeInTheDocument()
    expect(screen.queryByTestId("missing-guidelines")).not.toBeInTheDocument()
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
      min_pages: null,
      max_pages: null,
    })
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          url === "/api/admin/guidelines/versions/v2/publish" && init?.method === "POST",
      ),
    ).toBe(true)
  })

  describe("a rubric drafted from the regulation", () => {
    const drafted = [
      "> Szkic Corvusa z pliku „Zarządzenie.pdf”.",
      "## Elementy pracy",
      "### Wstęp",
      "- cel pracy (§ 3)",
      "## Wymogi formalne",
      "- objętość sugerowana",
      "## Co praca ma wykazać",
      "- logiczny tok wywodu",
      "## Waga uchybień",
      "- brak wstępu",
    ].join("\n")

    function backend(state: { drafting: boolean; rubric: string }) {
      const draft = {
        ...VERSION,
        status: "draft" as const,
        published_at: null,
        rubric_md: "",
        thresholds: { min_sources: null, min_foreign_sources: null, min_body_chars: null, max_body_chars: null },
      }
      return (url: string, init?: RequestInit): Promise<Response> => {
        if (url === "/api/settings/api-key/status")
          return Promise.resolve(json({ configured: true, providers: ["claude"] }))
        if (url === "/api/models") return Promise.resolve(json({ byok: { claude: "claude-sonnet-5-5" } }))
        if (url.endsWith("/draft-rubric")) {
          state.drafting = true
          return Promise.resolve(json({ ...draft, drafting: true }, 202))
        }
        if (url === "/api/admin/guidelines/versions/v2" && !init?.method) {
          return Promise.resolve(
            json({
              ...draft,
              drafting: state.drafting,
              rubric_md: state.rubric,
              thresholds: state.rubric ? { ...draft.thresholds, min_sources: 25 } : draft.thresholds,
            }),
          )
        }
        return Promise.resolve(json(draft))
      }
    }

    it("starts the draft on the admin's key and shows the rubric once it is in", async () => {
      const state = { drafting: false, rubric: "" }
      fetchMock.mockImplementation(backend(state))

      withSWR(<GuidelineDraftEditor versionId="v2" onDone={vi.fn()} />)

      const start = await screen.findByTestId("draft-rubric")
      await waitFor(() => expect(start).toBeEnabled())
      await userEvent.click(start)

      expect(await screen.findByTestId("drafting")).toBeInTheDocument()
      const post = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/draft-rubric"))
      expect(JSON.parse(post![1].body as string)).toEqual({ provider: "claude" })
      expect(screen.getByRole("button", { name: "Opublikuj" })).toBeDisabled()

      state.drafting = false
      state.rubric = drafted
      expect(await screen.findByTestId("rubric-elements", {}, { timeout: 5000 })).toHaveTextContent(
        "cel pracy (§ 3)",
      )
      expect(screen.getByLabelText("Minimalna liczba źródeł")).toHaveValue(25)
      expect(screen.queryByTestId("drafting")).not.toBeInTheDocument()
    }, 10000)

    it("says why a draft failed", async () => {
      fetchMock.mockImplementation((url: string) =>
        Promise.resolve(
          url === "/api/admin/guidelines/versions/v2"
            ? json({ ...VERSION, status: "draft", drafting: false, drafting_error: "no credits" })
            : json({ configured: true, providers: ["claude"], byok: {} }),
        ),
      )

      withSWR(<GuidelineDraftEditor versionId="v2" onDone={vi.fn()} />)

      expect(await screen.findByRole("alert")).toHaveTextContent("Szkic się nie udał: no credits")
    })

    it("builds new guidelines from a university, a kind of thesis and a file", async () => {
      fetchMock.mockImplementation((url: string, init?: RequestInit) => {
        if (url === "/api/settings/api-key/status")
          return Promise.resolve(json({ configured: true, providers: ["claude"] }))
        if (url === "/api/models") return Promise.resolve(json({ byok: {} }))
        if (url === "/api/guidelines/universities") return Promise.resolve(json([UE]))
        if (url === "/api/guidelines/sets") return Promise.resolve(json([]))
        if (url === "/api/admin/guidelines/sets" && init?.method === "POST")
          return Promise.resolve(json({ ...SET, id: "set9", versions: [] }, 201))
        if (url === "/api/admin/guidelines/sets/set9/versions")
          return Promise.resolve(json({ ...VERSION, id: "v9", status: "draft" }, 201))
        return Promise.resolve(json({ ...VERSION, id: "v9", status: "draft", drafting: true }))
      })

      const { container } = withSWR(<GuidelineAdmin />)

      const form = await screen.findByTestId("new-guidelines")
      await waitFor(() => expect(within(form).getAllByRole("option").length).toBeGreaterThan(3))
      await userEvent.selectOptions(within(form).getByLabelText("Uczelnia"), UE.id)
      await userEvent.selectOptions(within(form).getByLabelText("Typ pracy"), "master_article")
      await userEvent.type(within(form).getByLabelText("Nazwa zestawu"), "Magisterskie")
      const file = container.querySelector('input[aria-label="Regulamin"]') as HTMLInputElement
      await userEvent.upload(file, new File(["x"], "Zarządzenie.pdf", { type: "application/pdf" }))
      const start = within(form).getByTestId("start-from-regulation")
      await waitFor(() => expect(start).toBeEnabled())
      await userEvent.click(start)

      await waitFor(() =>
        expect(
          fetchMock.mock.calls.some(([url]) => url === "/api/admin/guidelines/versions/v9/draft-rubric"),
        ).toBe(true),
      )
      const order = fetchMock.mock.calls
        .filter(([, init]) => init?.method === "POST" || init?.method === "PUT")
        .map(([url]) => url)
      expect(order).toEqual([
        "/api/admin/guidelines/sets",
        "/api/admin/guidelines/sets/set9/versions",
        "/api/admin/guidelines/versions/v9/source",
        "/api/admin/guidelines/versions/v9/draft-rubric",
      ])
      const created = fetchMock.mock.calls.find(([url]) => url === "/api/admin/guidelines/sets")
      expect(JSON.parse(created![1].body as string)).toMatchObject({
        university_id: UE.id,
        thesis_type: "master_article",
        name: "Magisterskie",
      })
    })
  })

  describe("correcting and starting again", () => {
    it("shows the model's notes beside the draft, not in it, and discards on a second click", async () => {
      fetchMock.mockImplementation((url: string, init?: RequestInit) => {
        if (init?.method === "DELETE") return Promise.resolve(new Response(null, { status: 204 }))
        if (url === "/api/admin/guidelines/versions/v2")
          return Promise.resolve(
            json({ ...VERSION, status: "draft", draft_notes: ["Brak załącznika nr 3."] }),
          )
        return Promise.resolve(json({ configured: true, providers: ["claude"], byok: {} }))
      })
      const onDone = vi.fn()

      withSWR(<GuidelineDraftEditor versionId="v2" onDone={onDone} />)

      expect(await screen.findByTestId("draft-notes")).toHaveTextContent("Brak załącznika nr 3.")
      await userEvent.click(screen.getByTestId("discard-draft"))
      expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false)
      await userEvent.click(screen.getByRole("button", { name: "Na pewno odrzucić szkic?" }))

      await waitFor(() => expect(onDone).toHaveBeenCalled())
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) => url === "/api/admin/guidelines/versions/v2" && init?.method === "DELETE",
        ),
      ).toBe(true)
    })

    it("corrects a published set as a new version and deletes a set on a second click", async () => {
      fetchMock.mockImplementation((url: string, init?: RequestInit) => {
        if (url === "/api/guidelines/sets") return Promise.resolve(json([SET]))
        if (url === "/api/guidelines/universities") return Promise.resolve(json([UE]))
        if (url.endsWith("/corrections"))
          return Promise.resolve(json({ ...VERSION, id: "v3", version_no: 3, status: "draft" }, 201))
        if (init?.method === "DELETE") return Promise.resolve(new Response(null, { status: 204 }))
        return Promise.resolve(json({ ...VERSION, id: "v3", status: "draft", byok: {}, providers: [] }))
      })

      withSWR(<GuidelineAdmin />)

      const row = await screen.findByTestId("set-set1")
      await userEvent.click(within(row).getByRole("button", { name: "Popraw" }))
      await waitFor(() =>
        expect(
          fetchMock.mock.calls.some(([url]) => url === "/api/admin/guidelines/sets/set1/corrections"),
        ).toBe(true),
      )

      await userEvent.click(within(row).getByRole("button", { name: "Usuń zestaw" }))
      expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false)
      await userEvent.click(within(row).getByRole("button", { name: "Na pewno usunąć?" }))
      await waitFor(() =>
        expect(
          fetchMock.mock.calls.some(
            ([url, init]) => url === "/api/admin/guidelines/sets/set1" && init?.method === "DELETE",
          ),
        ).toBe(true),
      )
    })
  })
})
