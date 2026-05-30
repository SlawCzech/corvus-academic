import { NextResponse, type NextRequest } from "next/server"
import { decodeToken } from "@/lib/auth"

export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl
  const token = request.cookies.get("token")?.value

  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url))
  }

  if (pathname.startsWith("/admin")) {
    const payload = decodeToken(token)
    if (!payload || payload.role !== "ADMIN") {
      return NextResponse.redirect(new URL("/login", request.url))
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: ["/admin/:path*", "/analysis/:path*"],
}
