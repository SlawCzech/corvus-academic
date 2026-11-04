import { describe, expect, it } from "vitest"
import { resolveModel } from "@/lib/modelChoice"

describe("resolveModel", () => {
  it("takes a stored key when nothing was chosen, Claude first", () => {
    expect(resolveModel("", ["openai", "claude"]).provider).toBe("claude")
    expect(resolveModel("", ["openai"])).toMatchObject({
      selected: "byok:openai",
      provider: "openai",
      needsKey: false,
    })
  })

  it("keeps the provider that was chosen", () => {
    expect(resolveModel("byok:openai", ["claude", "openai"]).provider).toBe("openai")
  })

  it("treats a local model saved before ADR 0022 as no choice", () => {
    expect(resolveModel("local", ["claude"]).provider).toBe("claude")
    expect(resolveModel("gemma4:12b", ["claude"]).provider).toBe("claude")
  })

  it("cannot run without a key", () => {
    const choice = resolveModel("", [])
    expect(choice).toMatchObject({ selected: "", needsKey: true })
    expect(choice.provider).toBeUndefined()
  })

  it("does not move a removed key's runs onto the other provider", () => {
    const choice = resolveModel("byok:openai", ["claude"])
    expect(choice).toMatchObject({ needsKey: true, missingKey: "openai" })
    expect(choice.provider).toBeUndefined()
  })

  it("takes a preference at its word while the keys are still loading", () => {
    expect(resolveModel("byok:openai", undefined).provider).toBe("openai")
  })

  it("ignores a provider it does not know", () => {
    expect(resolveModel("byok:deepmind", ["claude"]).provider).toBe("claude")
  })
})
