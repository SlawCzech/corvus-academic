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
