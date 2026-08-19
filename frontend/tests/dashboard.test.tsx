import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { push, fetchDashboard } = vi.hoisted(() => ({ push: vi.fn(), fetchDashboard: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("../lib/dashboardApi", () => ({ fetchDashboard }));

import DashboardPage from "../app/page";
import { initialDashboardPeriod } from "../lib/dashboardDates";

const response = {
  period: { from_date: "2026-08-01", to_date: "2026-08-19", timezone: "Asia/Tokyo" },
  basic_metrics: {
    access_count: 10, access_user_count: 4, chat_count: 6, chat_user_count: 3,
    average_chats_per_day: 0.3, average_chats_per_user: 2,
    response_count: 8, average_responses_per_chat: 1.3, average_responses_per_user: 2.7,
    response_time: { average_seconds: 2.25, minimum_seconds: 1, maximum_seconds: 4 },
    valid_answer_count: 7, no_answer_count: 1, answer_rate: 87.5,
    good_count: 3, bad_count: 1, unrated_count: 3, satisfaction_rate: 75,
    comment_count: 2, good_comment_count: 1, bad_comment_count: 1,
  },
  answer_types: {
    total_count: 8, faq_count: 4, faq_rate: 50, generated_ai_count: 3, generated_ai_rate: 37.5, no_answer_count: 1,
  },
  time_buckets: ["9-12", "12-15", "15-18", "18-21", "21-0", "0-3", "3-6", "6-9"].map((key, index) => ({
    key, label: `${key}時`, chat_count: index, response_count: index + 1,
  })),
  weekday_buckets: ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"].map((key, index) => ({
    key, label: "月火水木金土日"[index], chat_count: index, response_count: index + 1,
  })),
};

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date("2026-08-19T03:00:00Z"));
  push.mockReset();
  fetchDashboard.mockReset();
  fetchDashboard.mockResolvedValue(response);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("CB-201 Dashboard", () => {
  it("JSTの当月1日から当日を初期表示し1回取得する", async () => {
    expect(initialDashboardPeriod(new Date("2026-08-31T16:30:00Z"))).toEqual({ from: "2026-09-01", to: "2026-09-01" });
    render(<DashboardPage />);
    expect((screen.getByLabelText("From") as HTMLInputElement).value).toBe("2026-08-01");
    expect((screen.getByLabelText("To") as HTMLInputElement).value).toBe("2026-08-19");
    await waitFor(() => expect(fetchDashboard).toHaveBeenCalledWith("2026-08-01", "2026-08-19"));
    expect(fetchDashboard).toHaveBeenCalledTimes(1);
  });

  it("期間変更だけでは取得せず、集計ボタンで再取得する", async () => {
    render(<DashboardPage />);
    await screen.findByText("基本指標");
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-08-05" } });
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-08-10" } });
    expect(fetchDashboard).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "集計" }));
    await waitFor(() => expect(fetchDashboard).toHaveBeenLastCalledWith("2026-08-05", "2026-08-10"));
    expect(fetchDashboard).toHaveBeenCalledTimes(2);
  });

  it("全指標、8時間帯、7曜日、小数1桁、新HeaderとSidebarを表示する", async () => {
    render(<DashboardPage />);
    await screen.findByText("基本指標");
    expect(screen.getByRole("heading", { name: "ダッシュボード" })).not.toBeNull();
    expect(screen.getByText("チャット回答種別利用状況")).not.toBeNull();
    expect(screen.getByText("87.5%")).not.toBeNull();
    expect(screen.getByText("2.3")).not.toBeNull();
    expect(screen.getAllByText(/時$/)).toHaveLength(8);
    for (const label of "月火水木金土日") expect(screen.getByText(label)).not.toBeNull();
    expect(screen.getByRole("button", { name: "チャットサイト" })).not.toBeNull();
    expect(screen.getByRole("button", { name: "サイドメニューを閉じる" })).not.toBeNull();
  });

  it("nullを横線表示し、0件を0として表示する", async () => {
    fetchDashboard.mockResolvedValueOnce({
      ...response,
      basic_metrics: {
        ...response.basic_metrics,
        access_count: 0,
        average_chats_per_day: null,
        answer_rate: null,
        satisfaction_rate: null,
        response_time: { average_seconds: null, minimum_seconds: null, maximum_seconds: null },
      },
      answer_types: { ...response.answer_types, faq_rate: null, generated_ai_rate: null },
    });
    render(<DashboardPage />);
    await screen.findByText("基本指標");
    expect(screen.getAllByText("－").length).toBeGreaterThanOrEqual(6);
    expect(screen.getAllByText("0").length).toBeGreaterThan(0);
  });

  it("API失敗を0件にせず表示し、再集計できる", async () => {
    fetchDashboard.mockRejectedValueOnce(new Error("開始日は終了日以前を指定してください。")).mockResolvedValueOnce(response);
    render(<DashboardPage />);
    expect((await screen.findByRole("alert")).textContent).toContain("開始日は終了日以前を指定してください。");
    expect(screen.queryByText("基本指標")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "集計" }));
    expect(await screen.findByText("基本指標")).not.toBeNull();
  });
});
