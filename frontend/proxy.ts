import { NextRequest, NextResponse } from "next/server";

const TOKEN_COOKIE = "fraudlens_token";
const PUBLIC_PATHS = ["/", "/login", "/signup", "/attack"];

/** Sends a visitor without a session cookie (set at sign-in, see lib/auth.ts) from any console page to
 * /login. The landing, sign-in, sign-up and attack pages stay public. This is navigation only: the API
 * verifies the token on every request (fraudlens/api/deps.py). */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (PUBLIC_PATHS.includes(pathname)) {
    return NextResponse.next();
  }

  const token = request.cookies.get(TOKEN_COOKIE)?.value;
  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname + request.nextUrl.search);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|fonts/|backend/).*)"],
};
