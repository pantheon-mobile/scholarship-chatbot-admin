import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  completeTrackedInteraction: vi.fn(), fetchChatConfig: vi.fn(), fetchChatHistory: vi.fn(),
  fetchChatHistoryDetail: vi.fn(), recordChatAccess: vi.fn(), sendChatMessage: vi.fn(),
  startTrackedChat: vi.fn(), startTrackedInteraction: vi.fn(), submitFeedback: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("../components/auth/AuthProvider", () => ({
  useAuth: () => ({ user: { subject: "staff-001", display_name: "開発 職員", role: "staff", site: "faculty" }, logout: vi.fn() }),
}));
vi.mock("../lib/chatApi", () => api);

import ChatPage from "../app/chat/page";

beforeEach(() => {
  Object.values(api).forEach((mock) => mock.mockReset());
  api.fetchChatConfig.mockResolvedValue({
    title: "試験チャット", initial_message: "最初の案内", input_placeholder: "質問を入力", question_max_length: 200,
    frame_color: "#171a1d", bot_icon_url: null, history_enabled: true, maintenance_enabled: false,
    maintenance_message: "保守中", good_message: "Good理由", bad_message: "Bad理由",
    good_options: ["分かりやすい"], bad_options: ["回答が違う"],
  });
  api.fetchChatHistory.mockResolvedValue([{ id: "11111111-1111-4111-8111-111111111111", title: "過去の質問", started_at: "2026-09-03T00:00:00Z", updated_at: "2026-09-03T00:01:00Z" }]);
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

  it("利用者名ボタンからIDとログアウトメニューを表示する", () => {
    render(<ChatPage />);
    expect(screen.queryByRole("button", { name: "ログアウト" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "開発 職員 ▾" }));
    expect(screen.getByText("ID：staff-001")).toBeTruthy();
    expect(screen.getByRole("button", { name: "閉じる" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "ログアウト" })).toBeTruthy();
  });

  it("新規チャットでは案内メッセージ枠を表示しない", async () => {
    render(<ChatPage />);
    await waitFor(() => expect(api.fetchChatConfig).toHaveBeenCalled());
    expect(screen.queryByText("最初の案内")).toBeNull();
    expect(screen.queryByText("チャットボット")).toBeNull();
  });
});
