import { DashboardApiError, DashboardResponse } from "@/types/dashboard";

const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchDashboard(fromDate: string, toDate: string): Promise<DashboardResponse> {
  const parameters = new URLSearchParams({ from: fromDate, to: toDate });
  const response = await fetch(`${apiBase}/api/v1/dashboard?${parameters}`, { cache: "no-store" });
  if (!response.ok) {
    let message = "ダッシュボードの集計に失敗しました。";
    let code: string | undefined;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (body.detail) {
        message = body.detail.message ?? message;
        code = body.detail.code;
      }
    } catch {}
    throw new DashboardApiError(message, response.status, code);
  }
  return response.json();
}
