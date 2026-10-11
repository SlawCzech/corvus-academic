/**
 * What an action runs on: one of the promoter's own provider keys, or a
 * model on the local server.
 *
 * The choice is kept as one string, because that is what the preference in
 * `aiDefaults` and the `<select>` both hold:
 *
 *   ""             nothing chosen yet — a stored key if there is one
 *                  (Claude first), otherwise the default local model
 *   "byok:claude"  the promoter's key for that provider
 *   "local"        the default local model, chosen on purpose
 *   "gemma4:12b"   a local model by its tag
 *
 * A server can switch local models off (ADR 0013). Then only keys are
 * offered, and without one nothing can run — `needsKey` says so.
 */

import type { ModelCatalog } from "@/lib/api.types"

export type Provider = "claude" | "openai"

export const PROVIDERS: readonly Provider[] = ["claude", "openai"]

export const PROVIDER_LABELS: Record<Provider, string> = {
  claude: "Claude (Anthropic)",
  openai: "OpenAI",
}

export const LOCAL_DEFAULT = "local"

const BYOK_PREFIX = "byok:"

export function byokValue(provider: Provider): string {
  return `${BYOK_PREFIX}${provider}`
}

function isProvider(value: string): value is Provider {
  return (PROVIDERS as readonly string[]).includes(value)
}

export interface ResolvedModel {
  /** The option to show as selected — always a concrete one, never "". */
  selected: string
  /** Set when the run goes on the promoter's own key. */
  provider?: Provider
  /** A local model tag; undefined leaves the default to the server. */
  model?: string
  /** A saved local model that is no longer on offer. */
  withdrawn: string | null
  /** A saved provider whose key has since been removed. */
  missingKey: Provider | null
  /** Nothing can run: the server has no local models and no key fits. */
  needsKey: boolean
}

/**
 * Turn a saved choice into what can actually run.
 *
 * A preference can outlive what it names — the admin withdraws a model, the
 * promoter removes a key. Sending it anyway would only get the action
 * refused, so it falls back to the default local model and says what it was.
 * Never to another paid provider: that is not a choice to make for someone.
 *
 * `catalog` and `keys` are undefined while they load; a preference is then
 * taken at its word rather than declared gone.
 */
export function resolveModel(
  value: string,
  catalog: ModelCatalog | undefined,
  keys: readonly string[] | undefined,
): ResolvedModel {
  const none = { withdrawn: null, missingKey: null, needsKey: false }
  const local: ResolvedModel = { selected: LOCAL_DEFAULT, ...none }

  if (catalog?.local_enabled === false) return keysOnly(value, keys)

  if (value === "") {
    const first = PROVIDERS.find((p) => keys?.includes(p))
    return first ? { selected: byokValue(first), provider: first, ...none } : local
  }
  if (value === LOCAL_DEFAULT) return local

  if (value.startsWith(BYOK_PREFIX)) {
    const provider = value.slice(BYOK_PREFIX.length)
    if (!isProvider(provider)) return local
    if (keys === undefined || keys.includes(provider)) {
      return { selected: value, provider, ...none }
    }
    return { ...local, missingKey: provider }
  }

  if (!catalog) return { selected: value, model: value, ...none }
  if (value === catalog.default) return local
  if (catalog.available.some((m) => m.name === value)) {
    return { selected: value, model: value, ...none }
  }
  return { ...local, withdrawn: value }
}

/**
 * The same choice on a server without local models: a key, or nothing.
 *
 * A saved local model is no longer a choice, so it counts as no choice at
 * all. A saved provider whose key is gone is not swapped for the other
 * provider — that would bill a different account than the one picked.
 */
function keysOnly(value: string, keys: readonly string[] | undefined): ResolvedModel {
  const none = { withdrawn: null, missingKey: null, needsKey: false }
  const blocked: ResolvedModel = { selected: "", ...none, needsKey: true }

  if (value.startsWith(BYOK_PREFIX)) {
    const provider = value.slice(BYOK_PREFIX.length)
    if (isProvider(provider)) {
      if (keys === undefined || keys.includes(provider)) {
        return { selected: value, provider, ...none }
      }
      return { ...blocked, missingKey: provider }
    }
  }
  const first = PROVIDERS.find((p) => keys?.includes(p))
  return first ? { selected: byokValue(first), provider: first, ...none } : blocked
}
