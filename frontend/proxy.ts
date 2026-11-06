import { NextResponse, type NextRequest } from "next/server"
import { PASSWORD_PAGE, isTokenExpired, getRole, homeFor, mustChangePassword } from "@/lib/auth"

// Screens behind a login, and the file links that need a renewed token.
const PROTECTED = [
  /^\/admin(\/|$)/,
  /^\/dashboard(\/|$)/,
  /^\/students(\/|$)/,
  /^\/reviews(\/|$)/,
  /^\/profile(\/|$)/,
  /^\/guidelines(\/|$)/,
  /^\/password$/,
  // File links are plain navigations: no API client stands behind them to
  // renew an expired token, so without this the browser shows a raw 401.
  /^\/api\/students\/[^/]+\/drafts\/[^/]+\/file$/,
  /^\/api\/students\/[^/]+\/fragments\/[^/]+\/file$/,
  /^\/api\/guidelines\/versions\/[^/]+\/source$/,
]

/**
 * The policy for one page view.
 *
 * Scripts run only with this request's nonce: Next.js puts it on its own
 * inline scripts, the theme script gets it from the layout, and
 * `'strict-dynamic'` lets the scripts they load run too. Styles allow
 * `'unsafe-inline'`: React writes `style` attributes, and an attribute
 * cannot carry a nonce. Development adds `'unsafe-eval'`, which React needs
 * there for its error overlay, and drops the upgrade to HTTPS.
 */
export function contentSecurityPolicy(nonce: string, isDev: boolean): string {
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' blob: data:",
    "font-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    ...(isDev ? [] : ["upgrade-insecure-requests"]),
  ].join("; ")
}

function guard(request: NextRequest): NextResponse | null {
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

  // A temporary password from an admin: the password page and nothing else
  // until it is replaced. `app` refuses the rest anyway; this saves the user
  // from screens that would only show errors.
  const temporary = mustChangePassword(accessToken!)
  if (temporary && pathname !== PASSWORD_PAGE) {
    return NextResponse.redirect(new URL(PASSWORD_PAGE, request.url))
  }
  if (!temporary && pathname === PASSWORD_PAGE) {
    return NextResponse.redirect(new URL(homeFor(role), request.url))
  }

  if (pathname.startsWith("/admin")) {
    if (role !== "admin") {
      return NextResponse.redirect(new URL("/login", request.url))
    }
  }

  // An admin has no roster: the promoter's screens send them to their own.
  if (role === "admin") {
    if (
      pathname.startsWith("/dashboard") ||
      pathname.startsWith("/students") ||
      pathname.startsWith("/reviews")
    ) {
      return NextResponse.redirect(new URL(homeFor(role), request.url))
    }
    // The catalog they manage is /admin/guidelines; a single version's page
    // (/guidelines/<id>) stays shared, the admin view links to it.
    if (pathname === "/guidelines") {
      return NextResponse.redirect(new URL("/admin/guidelines", request.url))
    }
  }

  return null
}

export function proxy(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl
  if (PROTECTED.some((pattern) => pattern.test(pathname))) {
    const redirect = guard(request)
    if (redirect) return redirect
  }
  // A file is not a page: it runs no script and needs no policy.
  if (pathname.startsWith("/api/")) return NextResponse.next()

  const nonce = Buffer.from(crypto.randomUUID()).toString("base64")
  const policy = contentSecurityPolicy(nonce, process.env.NODE_ENV === "development")
  // Next.js reads the policy off the request to find the nonce for its own
  // scripts; the layout reads `x-nonce` for the theme script.
  const requestHeaders = new Headers(request.headers)
  requestHeaders.set("x-nonce", nonce)
  requestHeaders.set("Content-Security-Policy", policy)
  const response = NextResponse.next({ request: { headers: requestHeaders } })
  response.headers.set("Content-Security-Policy", policy)
  return response
}

export const config = {
  matcher: [
    // Every page, prefetches included: a prefetch of a protected screen must
    // meet the same login check. Static assets carry no policy.
    "/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|ico|webmanifest)$).*)",
    "/api/students/:student/drafts/:draft/file",
    "/api/students/:student/fragments/:fragment/file",
    "/api/guidelines/versions/:version/source",
  ],
}
