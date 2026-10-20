import { NextRequest, NextResponse } from "next/server";

const TOKEN_COOKIE = "fraudlens_token";
const PUBLIC_PATHS = ["/", "/login", "/signup", "/attack"];

/** Gates every analyst-console page behind a session cookie set at login
 * (see lib/auth.ts's setSession). The landing page and auth pages stay
 * public — everything else (dashboard, case, cases, network, reports,
 * audit, insights) redirects to /login without a
 * valid-looking session. The token itself is still verified for real by
 * the backend on every write (see fraudlens/api/deps.py) — this
 * middleware only keeps a logged-out visitor from landing on analyst
 * pages in the first place. */
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
  matcher: ["/((?!_next/static|_next/image|favicon.ico|backend/).*)"],
};
