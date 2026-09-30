import { describe, expect, it } from "vitest"
import { getRefreshInterval } from "@/hooks/useAction"
import type { AgentAction } from "@/lib/api.types"

const base: AgentAction = {
  id: "a1",
  student_id: "s1",
  promotor_id: "p1",
  action_type: "propose_topic",
  status: "pending",
  task_id: "t1",
  detail: null,
  output: null,
  error: null,
  accepted: false,
  accepted_at: null,
  created_at: "2026-03-01T10:00:00Z",
  updated_at: "2026-03-01T10:00:00Z",
}

describe("getRefreshInterval", () => {
  it("polls while the action has not been dispatched yet", () => {
    expect(getRefreshInterval(undefined)).toBe(3000)
  })

  it("keeps polling a queued or running action", () => {
    expect(getRefreshInterval(base)).toBe(3000)
    expect(getRefreshInterval({ ...base, status: "running" })).toBe(3000)
  })

  it("stops once the agent is done with it", () => {
    expect(getRefreshInterval({ ...base, status: "completed" })).toBe(0)
    expect(getRefreshInterval({ ...base, status: "failed" })).toBe(0)
  })

  it("waits without polling while the promoter picks the findings", () => {
    expect(getRefreshInterval({ ...base, status: "awaiting_input" })).toBe(0)
  })

  it("stops once the promoter has cancelled it", () => {
    expect(getRefreshInterval({ ...base, status: "cancelled" })).toBe(0)
  })
})
