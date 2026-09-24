import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({
  user: { subject: "F0000003", display_name: "開発 職員", role: "staff", site: "faculty" },
}));
const reporting = vi.hoisted(() => ({ downloadChatHistory: vi.fn() }));
const chatApi = vi.hoisted(() => ({
  fetchChatConfig: vi.fn(),
  recordAdminAccess: vi.fn(),
}));
const router = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("../components/auth/AuthProvider", () => ({
  useAuth: () => ({ user: auth.user, logout: vi.fn() }),
}));
vi.mock("../lib/reportingApi", () => reporting);
vi.mock("../lib/chatApi", () => chatApi);

import ChatHistoryPage from "../app/chat-history/page";

beforeEach(() => {
  reporting.downloadChatHistory.mockReset().mockResolvedValue(undefined);
  chatApi.fetchChatConfig.mockReset().mockResolvedValue({
    admin_title: "試験管理サイト",
    header_icon_url: null,
  });
  chatApi.recordAdminAccess.mockReset().mockResolvedValue(undefined);
  router.push.mockReset();
});

afterEach(cleanup);

describe("CB-216 チャット履歴ダウンロード", () => {
  it("回答種別の末尾に回答NGを表示し、選択した条件でダウンロードする", async () => {
    render(<ChatHistoryPage />);
    const select = screen.getByRole("combobox", { name: "チャット回答種別：" });
    expect(Array.from((select as HTMLSelectElement).options).map((option) => option.text)).toEqual(["（全て）", "FAQ", "生成AI", "回答NG"]);
    fireEvent.change(select, { target: { value: "NO_ANSWER" } });
    fireEvent.click(screen.getByRole("button", { name: "履歴ダウンロード" }));
    await waitFor(() => expect(reporting.downloadChatHistory).toHaveBeenCalledWith(expect.objectContaining({ answerType: "NO_ANSWER" })));
  });

  it("職員には権限とログインIDを表示せず、本人限定条件はサーバーに委ねる", async () => {
    auth.user.role = "staff";
    render(<ChatHistoryPage />);

    expect(screen.queryByText("権限：")).toBeNull();
    expect(screen.queryByText("ログインID：")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "履歴ダウンロード" }));
    await waitFor(() => expect(reporting.downloadChatHistory).toHaveBeenCalledWith(expect.objectContaining({
      role: "",
      userIds: "",
    })));
  });

  it("システム管理者には権限とログインIDの検索条件を表示する", async () => {
    auth.user.role = "admin";
    render(<ChatHistoryPage />);

    await waitFor(() => expect(chatApi.fetchChatConfig).toHaveBeenCalled());
    expect(screen.getByText("権限：")).toBeTruthy();
    expect(screen.getByText("ログインID：")).toBeTruthy();
  });
});
