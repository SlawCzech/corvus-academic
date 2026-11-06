"use client"

import useSWR from "swr"
import { fetcher } from "@/lib/api.client"

export const HOME_UNIVERSITY_KEY = "/api/users/me/settings"

/**
 * The university whose guidelines the promoter sees first, or null.
 *
 * `undefined` while it loads: a picker waits rather than showing every
 * university for a moment and then narrowing.
 */
export function useHomeUniversity(): string | null | undefined {
  const { data, error } = useSWR<{ home_university_id: string | null }>(
    HOME_UNIVERSITY_KEY,
    fetcher,
  )
  if (error) return null
  return data === undefined ? undefined : (data.home_university_id ?? null)
}
