import { NextResponse, type NextRequest } from "next/server"
import { isTokenExpired, getRole, homeFor } from "@/lib/auth"

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

  const role = getRole(accessToken!)

  if (pathname.startsWith("/admin")) {
    if (role !== "admin") {
      return NextResponse.redirect(new URL("/login", request.url))
    }
  }

  // An admin has no roster: the promoter's screens send them to their own.
  if (role === "admin") {
    if (pathname.startsWith("/dashboard") || pathname.startsWith("/students")) {
      return NextResponse.redirect(new URL(homeFor(role), request.url))
    }
    // The catalog they manage is /admin/guidelines; a single version's page
    // (/guidelines/<id>) stays shared, the admin view links to it.
    if (pathname === "/guidelines") {
      return NextResponse.redirect(new URL("/admin/guidelines", request.url))
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    "/admin/:path*",
    "/dashboard/:path*",
    "/students/:path*",
    "/profile/:path*",
    "/guidelines/:path*",
    // File links are plain navigations: no API client stands behind them to
    // renew an expired token, so without this the browser shows a raw 401.
    "/api/students/:student/drafts/:draft/file",
    "/api/students/:student/fragments/:fragment/file",
    "/api/guidelines/versions/:version/source",
  ],
}
