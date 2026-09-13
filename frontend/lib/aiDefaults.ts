/**
 * The promoter's default model/language/review-tone, kept in the browser
 * only (no account-level setting yet — see CLAUDE.md's redesign plan).
 * `ActionPanel` reads this to pre-fill its per-run options; `ProfileAiDefaults`
 * writes it. Same key, same shape, genuinely "the same setting."
 */

import { useSyncExternalStore } from "react"

export interface AiDefaults {
  model: string
  language: string
  reviewTone: string
}

const STORAGE_KEY = "corvus:ai-defaults"

export const FALLBACK_AI_DEFAULTS: AiDefaults = {
  model: "",
  language: "pl",
  reviewTone: "auto",
}

export function readAiDefaults(): AiDefaults {
  if (typeof window === "undefined") return FALLBACK_AI_DEFAULTS
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return FALLBACK_AI_DEFAULTS
    return { ...FALLBACK_AI_DEFAULTS, ...(JSON.parse(raw) as Partial<AiDefaults>) }
  } catch {
    return FALLBACK_AI_DEFAULTS
  }
}

const listeners = new Set<() => void>()

function subscribeAiDefaults(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function writeAiDefaults(defaults: AiDefaults): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(defaults))
  } catch {
    // Private mode / storage disabled — the setting just won't persist.
  }
  listeners.forEach((l) => l())
}

/**
 * The current defaults, kept in sync with `writeAiDefaults` calls anywhere
 * in the app — no effect needed: `useSyncExternalStore` already renders the
 * server/first-paint snapshot on hydration, then swaps in the real one.
 */
export function useAiDefaults(): AiDefaults {
  return useSyncExternalStore(
    subscribeAiDefaults,
    readAiDefaults,
    () => FALLBACK_AI_DEFAULTS,
  )
}
