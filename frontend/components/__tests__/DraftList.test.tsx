import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import DraftList from "../students/DraftList"
import type { ThesisDraft } from "@/lib/api.types"

/**
 * Versions used to be a read-only list of names. Now a promoter can download
 * the original, mark the final version (which schedules the others for
 * deletion) and delete one — and a deleted version must stay listed as a trace.
 */
function draft(n: number, overrides: Partial<ThesisDraft> = {}): ThesisDraft {
  return {
    id: `d${n}`,
    student_id: "s1",
    version_number: n,
    filename: `praca_v${n}.docx`,
    pages: 1,
    format: "docx",
    char_count: 84300,
    preview: "",
    uploaded_by: "p1",
    created_at: "2026-09-01T10:00:00Z",
    has_file: true,
    file_size: 2 * 1024 * 1024,
    file_sha256: "ab",
    is_accepted: false,
    purged_at: null,
    purge_due_at: null,
    ...overrides,
  }
}

describe("DraftList", () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock)
    fetchMock.mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("links the original file for download", () => {
    render(<DraftList studentId="s1" drafts={[draft(1)]} onChange={() => {}} />)

    const link = screen.getByRole("link", { name: "Pobierz plik" })
    expect(link).toHaveAttribute("href", "/api/students/s1/drafts/d1/file")
  })

  it("shows the final version and when the others will be deleted", () => {
    render(
      <DraftList
        studentId="s1"
        drafts={[
          draft(2, { is_accepted: true }),
          draft(1, { purge_due_at: "2026-10-15T10:00:00Z" }),
        ]}
        onChange={() => {}}
      />,
    )

    expect(within(screen.getByTestId("draft-2")).getByText("wersja finalna")).toBeInTheDocument()
    expect(screen.getByTestId("draft-1")).toHaveTextContent("Zostanie usunięta 15.10.2026")
  })

  it("keeps a purged version as a trace with nothing left to act on", () => {
    render(
      <DraftList
        studentId="s1"
        drafts={[draft(1, { purged_at: "2026-10-15T10:00:00Z", has_file: false })]}
        onChange={() => {}}
      />,
    )

    const row = screen.getByTestId("draft-1")
    expect(row).toHaveTextContent("Treść usunięta 15.10.2026")
    expect(row).toHaveTextContent("84 300 znaków")
    expect(within(row).queryByRole("link")).not.toBeInTheDocument()
    expect(within(row).queryByRole("button")).not.toBeInTheDocument()
  })

  it("accepts a version and hands back the updated list", async () => {
    const updated = [draft(1, { is_accepted: true })]
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(updated), { status: 200 }))
    const onChange = vi.fn()
    render(<DraftList studentId="s1" drafts={[draft(1)]} onChange={onChange} />)

    await userEvent.click(screen.getByRole("button", { name: "Zaakceptuj jako finalną" }))

    await waitFor(() => expect(onChange).toHaveBeenCalledWith(updated))
    expect(fetchMock).toHaveBeenCalledWith("/api/students/s1/drafts/d1/accept", {
      method: "POST",
    })
  })

  it("asks before deleting, and only deletes on confirmation", async () => {
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
    render(<DraftList studentId="s1" drafts={[draft(1)]} onChange={() => {}} />)

    await userEvent.click(screen.getByRole("button", { name: "Usuń wersję" }))
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByText(/Usunąć treść i plik tej wersji na stałe/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole("button", { name: "Usuń" }))

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith("/api/students/s1/drafts/d1", {
        method: "DELETE",
      }),
    )
  })

  it("shows why a change was refused", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Not found: d1" }), { status: 404 }),
    )
    render(<DraftList studentId="s1" drafts={[draft(1)]} onChange={() => {}} />)

    await userEvent.click(screen.getByRole("button", { name: "Zaakceptuj jako finalną" }))

    expect(await screen.findByRole("alert")).toHaveTextContent("Not found: d1")
  })
})
