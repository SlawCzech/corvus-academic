import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { APP_URL } from "@/lib/appProxy";

/**
 * Revoke the session on `app`, then clear the cookies here.
 *
 * Clearing the cookies alone logs this browser out but leaves the access
 * token valid until it expires, for anyone holding a copy. `app` revokes it
 * from the Authorization header and the refresh token from its cookie — the
 * same places it reads them from on every other request.
 */
export async function POST(): Promise<Response> {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("access_token")?.value;
  const refreshToken = cookieStore.get("refresh_token")?.value;

  if (accessToken || refreshToken) {
    const headers: Record<string, string> = {};
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
    if (refreshToken) headers.Cookie = `refresh_token=${refreshToken}`;
    await fetch(`${APP_URL}/auth/logout`, { method: "POST", headers }).catch(
      () => {},
    );
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set("access_token", "", { maxAge: 0, path: "/" });
  response.cookies.set("refresh_token", "", { maxAge: 0, path: "/" });
  return response;
}
