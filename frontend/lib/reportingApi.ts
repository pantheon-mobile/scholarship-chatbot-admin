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

export async function downloadUsageCsv(kind: "users" | "access-logs" | "operation-logs", from: string, to: string): Promise<void> {
  const query = new URLSearchParams({ from, to });
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
