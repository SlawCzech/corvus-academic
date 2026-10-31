import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { SWRConfig } from "swr"
import WorkTimeline from "../students/WorkTimeline"
import { fragmentFeedbackDraft } from "@/lib/fragmentFeedback"
import type { AgentAction, FragmentEntry, FragmentReview, Timeline } from "@/lib/api.types"

const REVIEW: FragmentReview = {
  summary: "Fragment omawia dobór próby.\n\nAutor opisuje ankietę.",
  answer: "Literatura wystarcza.",
  direction: "needs_changes",
  strengths: ["Dobrze postawiony problem."],
  changes: [{ point: "Uzasadnij dobór próby.", quote: "próba" }],
  additions: ["Opis narzędzia."],
  addressed: [],
  next_step: "Dopisać narzędzie badawcze.",
}

function action(status: string, output: FragmentReview | null): AgentAction {
  return {
    id: "a1",
    student_id: "s1",
    promotor_id: "p1",
    action_type: "review_fragment",
    status,
    task_id: "t1",
    detail: null,
    output: output ? ({ output, summary: output.summary } as never) : null,
    error: null,
    accepted: false,
    accepted_at: null,
    created_at: "2026-10-28T10:00:00Z",
    updated_at: "2026-10-28T10:00:00Z",
  } as AgentAction
}

function entry(fields: Partial<FragmentEntry> = {}): FragmentEntry {
  return {
    id: "f1",
    student_id: "s1",
    part_id: "part1",
    round_number: 1,
    received_on: "2026-10-28",
    question: null,
    filename: "rozdz2.docx",
    format: "docx",
    pages: 3,
    char_count: 4200,
    preview: "Początek rozdziału",
    has_file: true,
    purged_at: null,
    review_action_id: "a1",
    verdict: null,
    feedback: null,
    feedback_at: null,
    created_at: "2026-10-28T10:00:00Z",
    part_name: "Rozdział 2",
    summary: REVIEW.summary,
    review: action("completed", REVIEW),
    ...fields,
  }
}

function timeline(fragment: FragmentEntry | null): Timeline {
  return {
    parts: [
      {
        id: "part1",
        student_id: "s1",
        name: "Rozdział 2",
        position: 1,
        due_on: null,
        rounds: 1,
        state: "awaiting_feedback",
      },
    ],
    events: fragment
      ? [{ kind: "fragment", on: "2026-10-28", fragment, note: null, draft: null }]
      : [],
  }
}

type Call = { url: string; method: string; body: unknown }
let calls: Call[] = []
let current: Timeline
let actionStatus = 202

function respond(url: string, init?: RequestInit): Response {
  const method = init?.method ?? "GET"
  const body = typeof init?.body === "string" ? JSON.parse(init.body) : init?.body
  calls.push({ url, method, body })
  const json = (data: unknown, status = 200): Response =>
    new Response(JSON.stringify(data), { status })
  if (url.endsWith("/timeline")) return json(current)
  if (url === "/api/models") {
    return json({
      default: "qwen3:30b-a3b",
      available: [],
      byok: { claude: "claude-sonnet-5-5" },
      local_available: false,
      local_enabled: false,
    })
  }
  if (url.endsWith("/api-key/status")) return json({ providers: ["claude"] })
  if (url.endsWith("/fragments") && method === "POST") return json(entry(), 201)
  if (url.endsWith("/actions")) {
    return actionStatus === 202
      ? json(action("pending", null), 202)
      : json({ detail: "nope" }, actionStatus)
  }
  if (url.endsWith("/feedback")) return json(entry({ verdict: "on_track" }))
  return json({})
}

beforeEach(() => {
  calls = []
  actionStatus = 202
  current = timeline(entry())
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => Promise.resolve(respond(url, init))),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function show(): void {
  render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <WorkTimeline studentId="s1" />
    </SWRConfig>,
  )
}

describe("fragmentFeedbackDraft", () => {
  it("reads as a note to the student, without the summary", () => {
    const text = fragmentFeedbackDraft(REVIEW)

    expect(text).toContain("Literatura wystarcza.")
    expect(text).toContain("Co działa:\n- Dobrze postawiony problem.")
    expect(text).toContain("Do zmiany:\n- Uzasadnij dobór próby.")
    expect(text).toContain("Następny krok: Dopisać narzędzie badawcze.")
    expect(text).not.toContain("Fragment omawia")
    expect(text).not.toContain("Co już poprawione")
  })
})

describe("WorkTimeline", () => {
  it("shows the summary, and the draft in the box with the AI's suggestion", async () => {
    show()

    const summary = await screen.findByTestId("fragment-summary")
    expect(summary).toHaveTextContent("Fragment omawia dobór próby.")
    const box = screen.getByLabelText<HTMLTextAreaElement>("Feedback dla studenta")
    expect(box.value).toContain("Uzasadnij dobór próby.")
    expect(screen.getByRole("button", { name: "Do poprawy" })).toHaveAttribute(
      "aria-pressed",
      "true",
    )
    expect(screen.getByTestId("part-state")).toHaveTextContent("Czeka na Ciebie")
  })

  it("saves the promoter's words and the verdict they chose", async () => {
    const user = userEvent.setup()
    show()

    const box = await screen.findByLabelText("Feedback dla studenta")
    await user.clear(box)
    await user.type(box, "Moje słowa.")
    await user.click(screen.getByRole("button", { name: "Na razie OK" }))
    await user.click(screen.getByRole("button", { name: "Zapisz" }))

    await waitFor(() => {
      const saved = calls.find((c) => c.url.endsWith("/feedback"))
      expect(saved?.method).toBe("PUT")
      expect(saved?.body).toEqual({
        verdict: "on_track",
        feedback: "Moje słowa.",
        source_action_id: "a1",
        next_due_on: null,
      })
    })
  })

  it("copies what was saved to the clipboard", async () => {
    const user = userEvent.setup()
    const writeText = vi.fn(() => Promise.resolve())
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    })
    show()

    await screen.findByLabelText("Feedback dla studenta")
    await user.click(screen.getByRole("button", { name: "Zapisz i kopiuj do maila" }))

    await waitFor(() => expect(writeText).toHaveBeenCalled())
    const copied = writeText.mock.calls[0] as unknown as string[]
    expect(copied[0]).toContain("Uzasadnij dobór próby.")
    expect(await screen.findByText("Zapisano i skopiowano")).toBeInTheDocument()
  })

  it("asks for a verdict before saving", async () => {
    current = timeline(entry({ summary: null, review: null }))
    const user = userEvent.setup()
    show()

    await screen.findByLabelText("Feedback dla studenta")
    await user.click(screen.getByRole("button", { name: "Zapisz" }))

    expect(await screen.findByRole("alert")).toHaveTextContent("Wybierz ocenę")
    expect(calls.some((c) => c.url.endsWith("/feedback"))).toBe(false)
  })

  it("says the AI is reading while a run is unfinished", async () => {
    current = timeline(entry({ summary: null, review: action("running", null) }))
    show()

    expect(await screen.findByTestId("fragment-running")).toHaveTextContent(
      "AI czyta fragment",
    )
  })

  it("falls back to the opening of the text, and offers to run the AI", async () => {
    current = timeline(entry({ summary: null, review: null }))
    const user = userEvent.setup()
    show()

    await screen.findByText("Początek rozdziału")
    await user.click(await screen.findByRole("button", { name: "Uruchom AI" }))

    await waitFor(() => {
      const run = calls.find((c) => c.url.endsWith("/actions"))
      expect(run?.body).toMatchObject({
        action_type: "review_fragment",
        fragment_id: "f1",
      })
    })
  })

  it("keeps a saved fragment when the run cannot start", async () => {
    actionStatus = 409
    const user = userEvent.setup()
    current = timeline(null)
    show()

    await user.click(await screen.findByRole("button", { name: "Dodaj fragment" }))
    const form = screen.getByTestId("fragment-form")
    await user.type(within(form).getByLabelText("Część pracy"), "Rozdział 1")
    await user.click(within(form).getByRole("button", { name: "Wklej tekst" }))
    await user.type(within(form).getByLabelText("Tekst fragmentu"), "Treść.")
    await within(form).findByRole("option", { name: /Claude/ })
    await user.click(within(form).getByRole("button", { name: "Zapisz fragment" }))

    await waitFor(() =>
      expect(screen.queryByTestId("fragment-form")).not.toBeInTheDocument(),
    )
    expect(calls.some((c) => c.url.endsWith("/fragments"))).toBe(true)
    expect(calls.some((c) => c.url.endsWith("/actions"))).toBe(true)
  })

  it("closes an answered fragment to one line", async () => {
    current = timeline(entry({ verdict: "on_track", feedback: "Dobrze." }))
    show()

    const card = await screen.findByTestId("fragment-card")
    expect(within(card).getByText("Na razie OK")).toBeInTheDocument()
    expect(screen.queryByLabelText("Feedback dla studenta")).not.toBeInTheDocument()
  })
})
