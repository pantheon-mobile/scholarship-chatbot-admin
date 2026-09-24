import { describe, it, expect } from "vitest";
import { safeCitationUrl } from "@/lib/citationUrl";

describe("citation URL validation", () => {
  it("rejects executable schemes and ambiguous URLs", () => {
    for (const value of ["javascript:alert(1)", "data:text/html,test", "//example.com", "https://user:pass@example.com", "https://example.com\\@evil.test", "java\nscript:alert(1)"])
      expect(safeCitationUrl(value)).toBeNull();
  });
  it("allows https and the source download route", () => {
    expect(safeCitationUrl("https://example.com/file")).toBe("https://example.com/file");
    expect(safeCitationUrl("/api/v1/chat/sources/12/download")).toContain("/api/v1/chat/sources/12/download");
  });
});
