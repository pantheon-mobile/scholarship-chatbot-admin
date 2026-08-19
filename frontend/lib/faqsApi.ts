import { FaqCreate, FaqDetail, FaqFilters, FaqListResponse, FaqApiError } from "@/types/faq";

const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function queryString(filters: FaqFilters, includePaging = true) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (!includePaging && (key === "page" || key === "page_size")) return;
    if (value !== "" && value !== null && value !== undefined) params.set(key, String(value));
  });
  return params.toString();
}

async function parseError(response: Response, fallback: string): Promise<never> {
  let message = fallback;
  let code: string | undefined;
  try {
    const body = await response.json();
    if (typeof body.detail === "string") message = body.detail;
    else if (body.detail) {
      message = body.detail.message ?? fallback;
      code = body.detail.code;
    }
  } catch {}
  throw new FaqApiError(message, response.status, code);
}

export async function fetchFaqs(filters: FaqFilters): Promise<FaqListResponse> {
  const response = await fetch(`${apiBase}/api/v1/faqs?${queryString(filters)}`, { cache: "no-store" });
  if (!response.ok) return parseError(response, "FAQ一覧の取得に失敗しました。");
  return response.json();
}

export async function createFaq(values: FaqCreate): Promise<FaqDetail> {
  const response = await fetch(`${apiBase}/api/v1/faqs`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values),
  });
  if (!response.ok) return parseError(response, "FAQの登録に失敗しました。");
  return response.json();
}

export async function deleteFaq(id: number, version: number): Promise<void> {
  const response = await fetch(`${apiBase}/api/v1/faqs/${id}?version=${version}`, { method: "DELETE" });
  if (!response.ok) return parseError(response, "FAQの削除に失敗しました。");
}

export async function bulkDeleteFaqs(items: Array<{ id: number; version: number }>): Promise<number> {
  const response = await fetch(`${apiBase}/api/v1/faqs/bulk-delete`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items }),
  });
  if (!response.ok) return parseError(response, "選択したFAQの削除に失敗しました。");
  return (await response.json()).deleted_count;
}

export async function exportFaqs(filters: FaqFilters): Promise<Blob> {
  const response = await fetch(`${apiBase}/api/v1/faqs/export?${queryString(filters, false)}`);
  if (!response.ok) return parseError(response, "FAQ一覧のダウンロードに失敗しました。");
  return response.blob();
}
