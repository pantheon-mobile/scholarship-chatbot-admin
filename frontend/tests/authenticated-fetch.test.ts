import { afterEach, describe, expect, it, vi } from "vitest";

import { authenticatedFetch } from "../lib/authenticatedFetch";

afterEach(() => vi.unstubAllGlobals());

describe("authenticatedFetch", () => {
  it("管理APIへセッションCookieを送信する", async () => {
    const request = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    vi.stubGlobal("fetch", request);

    await authenticatedFetch("http://localhost:8000/api/v1/dashboard", {
      cache: "no-store",
    });

    expect(request).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/dashboard",
      { cache: "no-store", credentials: "include" },
    );
  });

  it("呼び出し側がcredentialsを指定してもincludeを優先する", async () => {
    const request = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    vi.stubGlobal("fetch", request);

    await authenticatedFetch("/api/v1/faqs", { credentials: "omit" });

    expect(request).toHaveBeenCalledWith(
      "/api/v1/faqs",
      { credentials: "include" },
    );
  });
});
