import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  completeTrackedInteraction: vi.fn(), deleteChatHistory: vi.fn(), fetchChatConfig: vi.fn(), fetchChatHistory: vi.fn(),
  fetchChatHistoryDetail: vi.fn(), recordChatAccess: vi.fn(), sendChatMessage: vi.fn(),
  startTrackedChat: vi.fn(), startTrackedInteraction: vi.fn(), submitFeedback: vi.fn(), updateChatHistoryTitle: vi.fn(),
}));
const router = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("../components/auth/AuthProvider", () => ({
  useAuth: () => ({ user: { subject: "staff-001", display_name: "開発 職員", role: "staff", site: "faculty" }, logout: vi.fn() }),
}));
vi.mock("../lib/chatApi", () => api);

import ChatPage from "../app/chat/page";

beforeEach(() => {
  router.push.mockReset();
  Object.values(api).forEach((mock) => mock.mockReset());
  api.fetchChatConfig.mockResolvedValue({
    title: "試験チャット", initial_message: "最初の案内", input_placeholder: "質問を入力", question_max_length: 200,
    frame_color: "#171a1d", bot_icon_url: null, history_enabled: true, maintenance_enabled: false,
    maintenance_message: "保守中", good_message: "Good理由", bad_message: "Bad理由",
    good_options: ["分かりやすい"], bad_options: ["回答が違う"],
  });
  api.fetchChatHistory.mockResolvedValue([{ id: "11111111-1111-4111-8111-111111111111", title: "過去の質問", started_at: "2026-09-03T00:00:00Z", updated_at: "2026-09-03T00:01:00Z" }]);
  api.updateChatHistoryTitle.mockResolvedValue({ id: "11111111-1111-4111-8111-111111111111", title: "変更後の名前", started_at: "2026-09-03T00:00:00Z", updated_at: "2026-09-03T00:01:00Z" });
  api.deleteChatHistory.mockResolvedValue(undefined);
  api.sendChatMessage.mockResolvedValue({ answer: "回答です", answer_type: "GENERATED_AI", bedrock_session_id: "bedrock-1", citations: [] });
  api.recordChatAccess.mockResolvedValue(undefined); api.startTrackedChat.mockResolvedValue(undefined); api.startTrackedInteraction.mockResolvedValue(undefined); api.completeTrackedInteraction.mockResolvedValue(undefined); api.submitFeedback.mockResolvedValue(undefined);
});

afterEach(cleanup);

describe("CB-101 チャットUI", () => {
  it("左メニュー、履歴、日時を表示し、Good理由をポップアップからDB APIへ送る", async () => {
    render(<ChatPage />);
    expect(screen.getByRole("button", { name: "サイドメニューを閉じる" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /新しいチャット/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /チャット履歴/ })).toBeTruthy();
    await screen.findByText("過去の質問");

    fireEvent.change(screen.getByLabelText("質問"), { target: { value: "申請期限は？" } });
    fireEvent.click(screen.getByRole("button", { name: "送信" }));
    await screen.findByText("回答です");
    expect(screen.getAllByRole("time").length).toBeGreaterThanOrEqual(2);

    fireEvent.click(screen.getByRole("button", { name: "Good" }));
    expect(screen.getByRole("dialog", { name: "回答へのGood評価" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("理由（任意）"), { target: { value: "分かりやすい" } });
    fireEvent.change(screen.getByLabelText("コメント（任意）"), { target: { value: "助かりました" } });
    fireEvent.click(screen.getByRole("button", { name: "送信する" }));
    await waitFor(() => expect(api.submitFeedback).toHaveBeenCalledWith(expect.any(String), "GOOD", "分かりやすい：助かりました"));
  });

  it("利用者名ボタンからIDと操作メニューを表示し、閉じるで管理画面へ戻る", () => {
    render(<ChatPage />);
    expect(screen.queryByRole("button", { name: "ログアウト" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "開発 職員 ▾" }));
    expect(screen.getByText("ID：staff-001")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "閉じる" }));
    expect(router.push).toHaveBeenCalledWith("/");
    expect(screen.queryByRole("button", { name: "ログアウト" })).toBeNull();
  });

  it("新規チャットでは案内メッセージ枠を表示しない", async () => {
    render(<ChatPage />);
    await waitFor(() => expect(api.fetchChatConfig).toHaveBeenCalled());
    expect(screen.queryByText("最初の案内")).toBeNull();
    expect(screen.queryByText("チャットボット")).toBeNull();
  });

  it("質問・回答本文を検索し、チャット名をEnterで保存またはキャンセルできる", async () => {
    render(<ChatPage />);
    await screen.findByText("過去の質問");
    expect(screen.queryByPlaceholderText("チャットを検索")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /チャット履歴/ }));
    const search = await screen.findByPlaceholderText("チャットを検索");
    fireEvent.change(search, { target: { value: "予約採用" } });
    await waitFor(() => expect(api.fetchChatHistory).toHaveBeenCalledWith("予約採用"));

    fireEvent.click(screen.getByRole("button", { name: "過去の質問のメニュー" }));
    fireEvent.click(screen.getByRole("button", { name: "編集" }));
    const title = screen.getByLabelText("チャット名");
    fireEvent.change(title, { target: { value: "変更後の名前" } });
    fireEvent.keyDown(title, { key: "Enter" });
    await waitFor(() => expect(api.updateChatHistoryTitle).toHaveBeenCalledWith("11111111-1111-4111-8111-111111111111", "変更後の名前"));
    await screen.findByText("変更後の名前");

    fireEvent.click(screen.getByRole("button", { name: "変更後の名前のメニュー" }));
    fireEvent.click(screen.getByRole("button", { name: "編集" }));
    fireEvent.click(screen.getByRole("button", { name: "キャンセル" }));
    expect(screen.queryByLabelText("チャット名")).toBeNull();
  });

  it("戻るアイコンで検索モードを終了して通常の履歴表示へ戻る", async () => {
    render(<ChatPage />);
    await screen.findByText("過去の質問");
    fireEvent.click(screen.getByRole("button", { name: /チャット履歴/ }));
    fireEvent.change(screen.getByPlaceholderText("チャットを検索"), { target: { value: "進学届" } });
    fireEvent.click(screen.getByRole("button", { name: "検索を終了" }));
    expect(screen.queryByPlaceholderText("チャットを検索")).toBeNull();
    expect(screen.getByText("最近の履歴")).toBeTruthy();
    await waitFor(() => expect(api.fetchChatHistory).toHaveBeenCalledWith(""));
  });

  it("共通ダイアログで削除確認し履歴を削除する", async () => {
    render(<ChatPage />);
    fireEvent.click(screen.getByRole("button", { name: /チャット履歴/ }));
    await screen.findByText("過去の質問");
    fireEvent.click(screen.getByRole("button", { name: "過去の質問のメニュー" }));
    fireEvent.click(screen.getByRole("button", { name: "削除" }));
    const dialog = screen.getByRole("dialog", { name: "チャットの削除" });
    expect(dialog.textContent).toContain("このチャットを削除しますか？");
    expect(dialog.textContent).toContain("このチャットに戻ることはできなくなります。");
    fireEvent.click(screen.getByRole("button", { name: /^削除$/ }));
    await waitFor(() => expect(api.deleteChatHistory).toHaveBeenCalledWith("11111111-1111-4111-8111-111111111111"));
  });
});
