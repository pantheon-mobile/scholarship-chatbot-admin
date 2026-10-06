import { describe, expect, it } from "vitest";
import { siteMetadata } from "../lib/siteMetadata";

describe("browser metadata", () => {
  it("uses the default title and runtime overrides", () => {
    expect(siteMetadata({}).title).toBe("Scholarship Chatbot");
    expect(siteMetadata({ SITE_BROWSER_TITLE: "試験", SITE_FAVICON_URL: "https://example.com/icon.png" })).toMatchObject({ title: "試験", icons: { icon: "https://example.com/icon.png" } });
    expect(siteMetadata({ SITE_FAVICON_URL: "/icons/school.ico" }).icons).toEqual({ icon: "/icons/school.ico" });
    expect(siteMetadata({ SITE_FAVICON_URL: "javascript:alert(1)" }).icons).toBeUndefined();
  });
});
