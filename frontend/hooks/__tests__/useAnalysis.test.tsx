import { renderHook, act } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { SWRConfig } from "swr"
import { getRefreshInterval, useAnalysis } from "../useAnalysis"
import type { TaskStatusResponse } from "@/lib/api.types"

vi.mock("@/lib/api.client", () => ({
  submitAnalysis: vi.fn(),
  fetchTaskStatus: vi.fn(),
}))

import { fetchTaskStatus, submitAnalysis } from "@/lib/api.client"

const mockSubmit = vi.mocked(submitAnalysis)
const mockFetch = vi.mocked(fetchTaskStatus)

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig value={{ dedupingInterval: 0, provider: () => new Map() }}>
      {children}
    </SWRConfig>
  )
}

const sampleResult = {
  evaluation_id: "e1",
  findings: [],
  scores: [],
  summary: "Good work",
  recommendation: "Approved",
  status: "done",
  error: null,
}

describe("getRefreshInterval", () => {
  it("returns 3000 when data is undefined", () => {
    expect(getRefreshInterval(undefined)).toBe(3000)
  })

  it("returns 3000 while analyzing", () => {
    const data: TaskStatusResponse = { status: "analyzing", result: null }
    expect(getRefreshInterval(data)).toBe(3000)
  })

  it("returns 0 when status is done", () => {
    const data: TaskStatusResponse = { status: "done", result: sampleResult }
    expect(getRefreshInterval(data)).toBe(0)
  })

  it("returns 0 when status is error", () => {
    const data: TaskStatusResponse = { status: "error", result: null }
    expect(getRefreshInterval(data)).toBe(0)
  })
})

describe("useAnalysis", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("starts in idle state", () => {
    const { result } = renderHook(() => useAnalysis(), { wrapper })
    expect(result.current.status).toBe("idle")
    expect(result.current.result).toBeNull()
    expect(result.current.error).toBeNull()
  })

  it("transitions to uploading then analyzing after submit", async () => {
    mockSubmit.mockResolvedValue({ task_id: "t1" })
    mockFetch.mockResolvedValue({ status: "analyzing", result: null })

    const { result } = renderHook(() => useAnalysis(), { wrapper })

    await act(async () => {
      await result.current.submit(
        new File(["pdf"], "thesis.pdf", { type: "application/pdf" }),
        { model: "qwen3:30b-a3b", mode: "full", review_tone: "auto", thesis_type: "bachelor" },
      )
    })

    expect(result.current.status).toBe("analyzing")
  })

  it("polling stops when status is done", async () => {
    vi.useFakeTimers()

    mockSubmit.mockResolvedValue({ task_id: "t2" })
    mockFetch
      .mockResolvedValueOnce({ status: "analyzing", result: null })
      .mockResolvedValueOnce({ status: "done", result: sampleResult })

    const { result } = renderHook(() => useAnalysis(), { wrapper })

    await act(async () => {
      await result.current.submit(
        new File(["pdf"], "thesis.pdf", { type: "application/pdf" }),
        { model: "qwen3:30b-a3b", mode: "full", review_tone: "auto", thesis_type: "bachelor" },
      )
    })

    // First SWR fetch (immediate on key set)
    await act(async () => {
      await vi.runAllTimersAsync()
    })

    // Advance 3s → second poll returns "done"
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000)
    })

    expect(result.current.status).toBe("done")
    expect(result.current.result).toEqual(sampleResult)

    const callsBefore = mockFetch.mock.calls.length

    // Advance another 6s — refreshInterval is 0, no more calls
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000)
    })

    expect(mockFetch.mock.calls.length).toBe(callsBefore)

    vi.useRealTimers()
  })

  it("polling stops when status is error", async () => {
    vi.useFakeTimers()

    mockSubmit.mockResolvedValue({ task_id: "t3" })
    mockFetch.mockResolvedValue({ status: "error", result: null })

    const { result } = renderHook(() => useAnalysis(), { wrapper })

    await act(async () => {
      await result.current.submit(
        new File(["pdf"], "thesis.pdf", { type: "application/pdf" }),
        { model: "qwen3:30b-a3b", mode: "full", review_tone: "auto", thesis_type: "bachelor" },
      )
    })

    await act(async () => {
      await vi.runAllTimersAsync()
    })

    expect(result.current.status).toBe("error")

    const callsBefore = mockFetch.mock.calls.length
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000)
    })
    expect(mockFetch.mock.calls.length).toBe(callsBefore)

    vi.useRealTimers()
  })

  it("sets error state when submit fails", async () => {
    mockSubmit.mockRejectedValue(new Error("Upload failed (503): Service down"))

    const { result } = renderHook(() => useAnalysis(), { wrapper })

    await act(async () => {
      await result.current.submit(
        new File(["pdf"], "thesis.pdf", { type: "application/pdf" }),
        { model: "qwen3:30b-a3b", mode: "full", review_tone: "auto", thesis_type: "bachelor" },
      )
    })

    expect(result.current.status).toBe("error")
    expect(result.current.error).toMatch(/upload failed/i)
  })
})
