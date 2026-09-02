import { describe, expect, it } from "vitest";
import { canAccessAdminPath } from "../lib/permissions";

describe("role permissions", () => {
  it("システム管理者は全管理画面へアクセスできる", () => {
    expect(canAccessAdminPath("admin", "/data-sources/files/new")).toBe(true);
    expect(canAccessAdminPath("admin", "/faq-classifications")).toBe(true);
    expect(canAccessAdminPath("admin", "/usage")).toBe(true);
  });

  it("職員はFAQと自分用チャット履歴を利用でき、管理者専用画面は利用できない", () => {
    expect(canAccessAdminPath("staff", "/")).toBe(true);
    expect(canAccessAdminPath("staff", "/faqs/12/edit")).toBe(true);
    expect(canAccessAdminPath("staff", "/chat-history")).toBe(true);
    expect(canAccessAdminPath("staff", "/data-sources")).toBe(false);
    expect(canAccessAdminPath("staff", "/categories/1/edit")).toBe(false);
    expect(canAccessAdminPath("staff", "/faq-classifications")).toBe(false);
    expect(canAccessAdminPath("staff", "/usage")).toBe(false);
  });
});
