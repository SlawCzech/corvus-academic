/**
 * What an action runs on: one of the promoter's own provider keys.
 *
 * The choice is kept as one string, because that is what the preference in
 * `aiDefaults` and the `<select>` both hold:
 *
 *   ""             nothing chosen yet — a stored key if there is one
 *                  (Claude first)
 *   "byok:claude"  the promoter's key for that provider
 *
 * Anything else — a local model saved before ADR 0022 — counts as no choice.
 * Without a key nothing can run, and `needsKey` says so.
 */

export type Provider = "claude" | "openai"

export const PROVIDERS: readonly Provider[] = ["claude", "openai"]

export const PROVIDER_LABELS: Record<Provider, string> = {
  claude: "Claude (Anthropic)",
  openai: "OpenAI",
}

const BYOK_PREFIX = "byok:"

export function byokValue(provider: Provider): string {
  return `${BYOK_PREFIX}${provider}`
}

function isProvider(value: string): value is Provider {
  return (PROVIDERS as readonly string[]).includes(value)
}

export interface ResolvedModel {
  /** The option to show as selected; "" when nothing can run. */
  selected: string
  /** The provider the run goes on, when there is one. */
  provider?: Provider
  /** A saved provider whose key has since been removed. */
  missingKey: Provider | null
  /** Nothing can run: no key fits. */
  needsKey: boolean
}

/**
 * Turn a saved choice into what can actually run.
 *
 * A saved provider whose key is gone is not swapped for the other provider —
 * that would bill a different account than the one picked.
 *
 * `keys` is undefined while it loads; a preference is then taken at its word
 * rather than declared gone.
 */
export function resolveModel(value: string, keys: readonly string[] | undefined): ResolvedModel {
  const none = { missingKey: null, needsKey: false }
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
