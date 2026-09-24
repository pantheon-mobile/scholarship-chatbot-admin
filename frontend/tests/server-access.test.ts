// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";
import { createHmac } from "node:crypto";
import { NextFetchEvent, NextRequest } from "next/server";
import { pageSurface, proxy } from "../proxy";

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

it("derives site from the requested page", () => {
  expect(pageSurface("/chat")).toBe("CHAT");
  expect(pageSurface("/faqs/12/edit")).toBe("ADMIN");
  expect(pageSurface("/")).toBe("ADMIN");
  expect(pageSurface("/sso/cpf")).toBeNull();
  expect(pageSurface("/api/v1/chat/config")).toBeNull();
});

it("signs a server event bound to the cookie, URL, body and forwarded metadata", async () => {
  vi.stubEnv("ACCESS_LOG_SIGNING_SECRET", "private-test-key");
  vi.stubEnv("ACCESS_LOG_API_URL", "https://configured.example/api/v1/analytics/accesses");
  vi.stubEnv("ACCESS_LOG_ORIGIN", "https://configured.example");
  const fetcher = vi.fn().mockResolvedValue({ ok: true });
  vi.stubGlobal("fetch", fetcher);
  const promises: Promise<unknown>[] = [];
  const event = { waitUntil: (p: Promise<unknown>) => promises.push(p) } as unknown as NextFetchEvent;
  proxy(new NextRequest("https://untrusted-host.example/chat", { headers: { cookie: "scholarship_session=token", "x-access-page": "/usage", "x-forwarded-for": "1.2.3.4, 8.8.8.8", "user-agent": "test" } }), event);
  await Promise.all(promises);
  const [url, options] = fetcher.mock.calls[0];
  expect(url).toBe("https://configured.example/api/v1/analytics/accesses");
  expect(options.headers["X-Access-Page"]).toBe("/chat");
  expect(JSON.parse(options.body).surface).toBe("CHAT");
  expect(JSON.parse(options.body).forwarded_for).toBe("1.2.3.4, 8.8.8.8");
  expect(options.headers["X-Access-Signature"]).toBe(createHmac("sha256", "private-test-key").update(`v1\ntoken\n/chat\n${options.body}`).digest("hex"));
});

it("does not record unauthenticated requests", () => {
  const event = { waitUntil: vi.fn() } as unknown as NextFetchEvent;
  proxy(new NextRequest("https://example.com/chat"), event);
  expect(event.waitUntil).not.toHaveBeenCalled();
});
