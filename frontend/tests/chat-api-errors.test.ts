import { afterEach, describe, expect, it, vi } from "vitest";
import { sendChatMessage, startTrackedInteraction, submitFeedback } from "../lib/chatApi";
import { QUESTION_REJECTED_MESSAGE } from "../lib/chatErrors";

afterEach(() => vi.unstubAllGlobals());

const senders = [
  () => startTrackedInteraction("session", "interaction", 1, "2026-10-13T00:00:00Z", '<img src=x onerror="console.log(1)"> テスト'),
  () => sendChatMessage('<img src=x onerror="console.log(1)"> テスト', "session", "interaction"),
];

describe.each(senders)("質問送信のエラー", (send) => {
  it("HTMLの403は原因を断定しない一般的な案内にし、本文を表示しない", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>403 Forbidden</html>", { status: 403, headers: { "Content-Type": "text/html; charset=utf-8" } })));
    await expect(send()).rejects.toThrow(QUESTION_REJECTED_MESSAGE);
  });
  it.each([401, 403, 429])("アプリのJSONエラー(%s)を維持する", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "アプリからの具体的な案内" }, { status })));
    await expect(send()).rejects.toThrow("アプリからの具体的な案内");
  });
  it("理由のないJSON 403ではHTMLの書き換えを案内しない", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({}, { status: 403 })));
    await expect(send()).rejects.toThrow(QUESTION_REJECTED_MESSAGE);
  });
  it("HTML 500と通信切断をWAF遮断として扱わない", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(new Response("<html>failure</html>", { status: 500, headers: { "Content-Type": "text/html" } })).mockRejectedValueOnce(new TypeError("Failed to fetch")));
    await expect(send()).rejects.not.toThrow(QUESTION_REJECTED_MESSAGE);
    await expect(send()).rejects.toThrow("Failed to fetch");
  });
});

it("評価の送信エラーを質問の案内に置き換えない", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("blocked", { status: 403, headers: { "Content-Type": "text/html" } })));
  await expect(submitFeedback("interaction", "BAD", "comment")).rejects.toThrow("利用状況を記録できませんでした。");
});
