import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { SWRConfig } from "swr"
import InProgressActions from "../InProgressActions"
import type { ActionInProgress } from "@/lib/api.types"

/**
 * The dashboard said five actions were running when two were. The list shows
 * which, since when, and lets the promoter clear the dead ones.
 */
const HOUR = 60 * 60 * 1000

function item(overrides: Partial<ActionInProgress>): ActionInProgress {
  const now = new Date().toISOString()
  return {
    id: "a1",
    student_id: "s1",
    student_name: "Julia Krzemień",
    action_type: "generate_review",
    status: "running",
    created_at: now,
    updated_at: now,
    ...overrides,
  }
}

const FRESH = item({ id: "fresh" })
const DEAD = item({
  id: "dead",
  student_id: "s2",
  student_name: "Jan Test",
  action_type: "propose_topic",
  status: "pending",
  created_at: new Date(Date.now() - 12 * 24 * HOUR).toISOString(),
})

describe("InProgressActions", () => {
  let listed: ActionInProgress[]
  const fetchMock = vi.fn()

  beforeEach(() => {
    listed = [DEAD, FRESH]
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === "DELETE") {
        const id = url.split("/")[5]
        listed = listed.filter((a) => a.id !== id)
        return Promise.resolve(new Response(null, { status: 204 }))
      }
      if (init?.method === "POST") {
        const id = url.split("/")[5]
        listed = listed.filter((a) => a.id !== id)
        return Promise.resolve(
          new Response(JSON.stringify({ id, status: "cancelled" }), { status: 200 }),
        )
      }
      return Promise.resolve(new Response(JSON.stringify(listed), { status: 200 }))
    })
    vi.stubGlobal("fetch", fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    fetchMock.mockReset()
  })

  function renderList(onChange = vi.fn()): void {
    render(
      <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        <InProgressActions onChange={onChange} />
      </SWRConfig>,
    )
  }

  it("says which actions, for whom and since when", async () => {
    renderList()

    const [dead, fresh] = await screen.findAllByTestId("in-progress-item")
    expect(dead).toHaveTextContent("Jan Test")
    expect(dead).toHaveTextContent("Propozycja tematu")
    expect(dead).toHaveTextContent("12 dni")
    expect(dead).toHaveTextContent("prawdopodobnie martwa")
    expect(fresh).toHaveTextContent("Julia Krzemień")
    expect(fresh).not.toHaveTextContent("martwa")
  })

  it("cancels a dead one after asking", async () => {
    const onChange = vi.fn()
    renderList(onChange)
    const [dead] = await screen.findAllByTestId("in-progress-item")

    await userEvent.click(within(dead!).getByRole("button", { name: "Przerwij" }))
    await userEvent.click(within(dead!).getByRole("button", { name: "Tak, przerwij" }))

    await waitFor(() => expect(screen.getAllByTestId("in-progress-item")).toHaveLength(1))
    expect(screen.queryByText("Jan Test")).not.toBeInTheDocument()
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST")
    expect(post?.[0]).toBe("/api/students/s2/actions/dead/cancel")
    expect(onChange).toHaveBeenCalled()
  })

  it("says so when nothing is running", async () => {
    listed = []
    renderList()
    expect(await screen.findByText("Nic się teraz nie liczy.")).toBeInTheDocument()
  })

  it("deletes a dead one outright", async () => {
    renderList()
    const [dead] = await screen.findAllByTestId("in-progress-item")

    await userEvent.click(within(dead!).getByRole("button", { name: "Usuń" }))
    await userEvent.click(within(dead!).getByRole("button", { name: "Tak, usuń" }))

    await waitFor(() => expect(screen.getAllByTestId("in-progress-item")).toHaveLength(1))
    const del = fetchMock.mock.calls.find(([, init]) => init?.method === "DELETE")
    expect(del?.[0]).toBe("/api/students/s2/actions/dead")
  })
})
