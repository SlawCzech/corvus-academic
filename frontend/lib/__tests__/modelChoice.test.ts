import { describe, expect, it } from "vitest"
import type { ModelCatalog } from "@/lib/api.types"
import { resolveModel } from "@/lib/modelChoice"

const CATALOG: ModelCatalog = {
  default: "qwen3:30b-a3b",
  available: [
    { name: "gemma4:12b", parameter_size: "11.9B" },
    { name: "qwen3:30b-a3b", parameter_size: "30.5B" },
  ],
  local_available: true,
  byok: { claude: "claude-sonnet-5", openai: "gpt-5" },
}

describe("resolveModel", () => {
  it("runs locally when nothing was chosen and there is no key", () => {
    expect(resolveModel("", CATALOG, [])).toEqual({
      selected: "local",
      withdrawn: null,
      missingKey: null,
    })
  })

  it("uses the stored key when nothing was chosen, Claude before OpenAI", () => {
    expect(resolveModel("", CATALOG, ["openai"]).provider).toBe("openai")
    const both = resolveModel("", CATALOG, ["openai", "claude"])
    expect(both.provider).toBe("claude")
    expect(both.selected).toBe("byok:claude")
  })

  it("honours a chosen provider over the other stored key", () => {
    const choice = resolveModel("byok:openai", CATALOG, ["claude", "openai"])
    expect(choice.provider).toBe("openai")
    expect(choice.model).toBeUndefined()
  })

  it("keeps a run local when that was chosen, key or no key", () => {
    const choice = resolveModel("local", CATALOG, ["claude"])
    expect(choice.provider).toBeUndefined()
    expect(choice.selected).toBe("local")
  })

  it("sends a chosen local model by its tag", () => {
    const choice = resolveModel("gemma4:12b", CATALOG, ["claude"])
    expect(choice).toMatchObject({ selected: "gemma4:12b", model: "gemma4:12b" })
    expect(choice.provider).toBeUndefined()
  })

  it("leaves the default model for the server to name", () => {
    const choice = resolveModel("qwen3:30b-a3b", CATALOG, [])
    expect(choice.selected).toBe("local")
    expect(choice.model).toBeUndefined()
  })

  it("falls back to the local default when a saved model was withdrawn", () => {
    const choice = resolveModel("llama2:7b", CATALOG, ["claude"])
    expect(choice).toMatchObject({ selected: "local", withdrawn: "llama2:7b" })
    // Never to the paid key: that is not a choice to make for someone.
    expect(choice.provider).toBeUndefined()
  })

  it("falls back to the local default when the chosen key was removed", () => {
    const choice = resolveModel("byok:openai", CATALOG, ["claude"])
    expect(choice).toMatchObject({ selected: "local", missingKey: "openai" })
    expect(choice.provider).toBeUndefined()
  })

  it("takes a preference at its word while the lists are still loading", () => {
    expect(resolveModel("byok:openai", undefined, undefined).provider).toBe("openai")
    expect(resolveModel("gemma4:12b", undefined, undefined).model).toBe("gemma4:12b")
  })

  it("ignores a provider it does not know", () => {
    expect(resolveModel("byok:deepmind", CATALOG, ["claude"]).selected).toBe("local")
  })
})
