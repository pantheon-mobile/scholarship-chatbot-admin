import { createHmac, randomUUID } from "node:crypto";
import { NextFetchEvent, NextRequest, NextResponse } from "next/server";

const adminRoots = new Set(["data-sources", "data-source-types", "categories", "faqs", "faq-classifications", "chat-history", "usage"]);

export function pageSurface(path: string): "CHAT" | "ADMIN" | null {
  if (path === "/chat" || path.startsWith("/chat/")) return "CHAT";
  if (path === "/" || adminRoots.has(path.split("/")[1])) return "ADMIN";
  return null;
}

export function proxy(request: NextRequest, event: NextFetchEvent) {
  const response = NextResponse.next();
  const path = request.nextUrl.pathname;
  const surface = pageSurface(path);
  const token = request.cookies.get("scholarship_session")?.value;
  if (request.method !== "GET" || !surface || !token) return response;
  const secret = process.env.ACCESS_LOG_SIGNING_SECRET;
  const endpoint = process.env.ACCESS_LOG_API_URL;
  const origin = process.env.ACCESS_LOG_ORIGIN;
  if (!secret || !endpoint || !origin) {
    console.error("Server access logging is not configured");
    return response;
  }
  const body = JSON.stringify({ id: randomUUID(), identity: { identity_kind: "AUTHENTICATED", identifier: "server-page-request" }, accessed_at: new Date().toISOString(), surface, forwarded_for: request.headers.get("x-forwarded-for") ?? "", user_agent: request.headers.get("user-agent") ?? "" });
  const signature = createHmac("sha256", secret).update(`v1\n${token}\n${path}\n${body}`).digest("hex");
  // Only a configured destination receives the cookie; never trust Host/Origin
  // supplied by a caller as the destination of this server-side request.
  event.waitUntil(fetch(endpoint, {
    method: "POST", redirect: "error", cache: "no-store", signal: AbortSignal.timeout(5000),
    headers: { "Content-Type": "application/json", Origin: origin,
      Cookie: `scholarship_session=${token}`, "X-Access-Page": path, "X-Access-Signature": signature,
      "X-Forwarded-For": request.headers.get("x-forwarded-for") ?? "",
      "User-Agent": request.headers.get("user-agent") ?? "" }, body,
  }).then((result) => {
    if (!result.ok && result.status !== 401) console.error("Server access logging failed", result.status);
  }).catch(() => { console.error("Server access logging request failed"); }));
  return response;
}

export const config = { matcher: ["/", "/chat/:path*", "/data-sources/:path*", "/data-source-types/:path*", "/categories/:path*", "/faqs/:path*", "/faq-classifications/:path*", "/chat-history/:path*", "/usage/:path*"] };
