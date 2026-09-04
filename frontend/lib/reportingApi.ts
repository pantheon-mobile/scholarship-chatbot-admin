import { ChatHistoryResponse } from "@/types/reporting";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";

async function message(response: Response, fallback: string) {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : fallback;
  } catch { return fallback; }
}

export async function fetchChatHistory(from: string, to: string, page = 1, pageSize = 20): Promise<ChatHistoryResponse> {
  const query = new URLSearchParams({ from, to, page: String(page), page_size: String(pageSize) });
  const response = await fetch(`${apiBase}/api/v1/chat-history?${query}`, { cache: "no-store", credentials: "include" });
  if (!response.ok) throw new Error(await message(response, "チャット履歴を取得できませんでした。"));
  return response.json();
}

export type ChatHistoryDownloadFilters = { from: string; to: string; answerType?: string; rating?: string; comment?: string; role?: string; userIds?: string };

export async function downloadChatHistory(filters: ChatHistoryDownloadFilters): Promise<void> {
  const query = new URLSearchParams({ from: filters.from, to: filters.to });
  if (filters.answerType) query.set("answer_type", filters.answerType);
  if (filters.rating) query.set("rating", filters.rating);
  if (filters.comment) query.set("comment", filters.comment);
  if (filters.role) query.set("role", filters.role);
  if (filters.userIds?.trim()) query.set("user_ids", filters.userIds.trim());
  const response = await fetch(`${apiBase}/api/v1/chat-history/export.xlsx?${query}`, { credentials: "include" });
  if (!response.ok) throw new Error(await message(response, "チャット履歴を取得できませんでした。"));
  const blob = await response.blob(); const disposition = response.headers.get("content-disposition") ?? "";
  const filename = disposition.match(/filename="?([^";]+)"?/)?.[1] ?? "history.xlsx";
  const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = filename; anchor.click(); URL.revokeObjectURL(url);
}

export type UsageDownloadFilters = {
  role?: string;
  surface?: string;
  userIds?: string;
  operationType?: string;
};

export async function downloadUsageCsv(kind: "users" | "access-logs" | "operation-logs", from: string, to: string, filters: UsageDownloadFilters = {}): Promise<void> {
  const query = new URLSearchParams({ from, to });
  if (filters.role) query.set("role", filters.role);
  if (filters.surface) query.set("surface", filters.surface);
  if (filters.userIds?.trim()) query.set("user_ids", filters.userIds.trim());
  if (filters.operationType) query.set("operation_type", filters.operationType);
  const response = await fetch(`${apiBase}/api/v1/usage/${kind}.csv?${query}`, { credentials: "include" });
  if (!response.ok) throw new Error(await message(response, "CSVを取得できませんでした。"));
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") ?? "";
  const filename = disposition.match(/filename="?([^";]+)"?/)?.[1] ?? `${kind}.csv`;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url; anchor.download = filename; anchor.click();
  URL.revokeObjectURL(url);
}
