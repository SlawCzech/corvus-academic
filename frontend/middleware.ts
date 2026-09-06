import { NextResponse, type NextRequest } from "next/server"
import { isTokenExpired, getRole } from "@/lib/auth"

export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl
  const accessToken = request.cookies.get("access_token")?.value
  const refreshToken = request.cookies.get("refresh_token")?.value

  if (!accessToken && !refreshToken) {
    return NextResponse.redirect(new URL("/login", request.url))
  }

  if ((!accessToken || isTokenExpired(accessToken)) && refreshToken) {
    const url = new URL("/api/auth/refresh", request.url)
    url.searchParams.set("redirect", pathname)
    return NextResponse.redirect(url)
  }

  if (pathname.startsWith("/admin")) {
    const role = getRole(accessToken!)
    if (role !== "ADMIN") {
      return NextResponse.redirect(new URL("/login", request.url))
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: ["/admin/:path*", "/students/:path*", "/profile/:path*"],
}
