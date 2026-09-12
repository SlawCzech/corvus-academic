/**
 * How long the access-token cookie is kept.
 *
 * Matched to ACCESS_TOKEN_EXPIRE_MINUTES in `app` (12 h). These two drifted
 * apart once — an 8 h cookie carrying a 15 min token — and the symptom was
 * not "please log in" but every API call failing while the page looked
 * logged in.
 */
export const ACCESS_COOKIE_MAX_AGE = 60 * 60 * 12

/** The refresh token outlives it by a month, and renews it silently. */
export const REFRESH_COOKIE_MAX_AGE = 60 * 60 * 24 * 30

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface TokenPayload {
  sub: string
  email: string
  role: string
  exp: number
}

export function decodeToken(token: string): TokenPayload | null {
  try {
    const parts = token.split(".")
    if (parts.length !== 3) return null
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/")
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4)
    return JSON.parse(atob(padded)) as TokenPayload
  } catch {
    return null
  }
}

export function isTokenExpired(token: string): boolean {
  const payload = decodeToken(token)
  if (!payload) return true
  return Date.now() / 1000 >= payload.exp
}

export function getRole(token: string): string | null {
  return decodeToken(token)?.role ?? null
}

export function getUserId(token: string): string | null {
  return decodeToken(token)?.sub ?? null
}
