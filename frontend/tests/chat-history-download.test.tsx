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
const maintenanceApi = vi.hoisted(() => ({
  fetchMaintenanceCapabilities: vi.fn(),
  purgeAllData: vi.fn(),
}));
const router = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("../components/auth/AuthProvider", () => ({
  useAuth: () => ({ user: auth.user, logout: vi.fn() }),
}));
vi.mock("../lib/reportingApi", () => reporting);
vi.mock("../lib/chatApi", () => chatApi);
vi.mock("../lib/maintenanceApi", () => maintenanceApi);

import ChatHistoryPage from "../app/chat-history/page";

beforeEach(() => {
  reporting.downloadChatHistory.mockReset().mockResolvedValue(undefined);
  chatApi.fetchChatConfig.mockReset().mockResolvedValue({
    admin_title: "試験管理サイト",
    header_icon_url: null,
  });
  chatApi.recordAdminAccess.mockReset().mockResolvedValue(undefined);
  maintenanceApi.fetchMaintenanceCapabilities.mockReset().mockResolvedValue({ bulk_purge_enabled: false });
  maintenanceApi.purgeAllData.mockReset().mockResolvedValue(undefined);
  router.push.mockReset();
});

afterEach(cleanup);

describe("CB-216 チャット履歴ダウンロード", () => {
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

    expect(screen.getByText("権限：")).toBeTruthy();
    expect(screen.getByText("ログインID：")).toBeTruthy();
    await waitFor(() => expect(maintenanceApi.fetchMaintenanceCapabilities).toHaveBeenCalled());
  });
});
