import { FaqCreate, FaqDetail, FaqFilters, FaqImportResponse, FaqImportRowError, FaqListResponse, FaqApiError, FaqUpdate } from "@/types/faq";

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
  let errors: FaqImportRowError[] = [];
  try {
    const body = await response.json();
    if (typeof body.detail === "string") message = body.detail;
    else if (body.detail) {
      message = body.detail.message ?? fallback;
      code = body.detail.code;
      errors = Array.isArray(body.detail.errors) ? body.detail.errors : [];
    }
  } catch {}
  throw new FaqApiError(message, response.status, code, errors);
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

export async function fetchFaq(id: number): Promise<FaqDetail> {
  const response = await fetch(`${apiBase}/api/v1/faqs/${id}`, { cache: "no-store" });
  if (!response.ok) return parseError(response, "FAQの取得に失敗しました。");
  return response.json();
}

export async function updateFaq(id: number, values: FaqUpdate): Promise<FaqDetail> {
  const response = await fetch(`${apiBase}/api/v1/faqs/${id}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values),
  });
  if (!response.ok) return parseError(response, "FAQの更新に失敗しました。");
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

export async function downloadFaqImportTemplate(): Promise<Blob> {
  const response = await fetch(`${apiBase}/api/v1/faqs/import-template`);
  if (!response.ok) return parseError(response, "FAQ登録フォーマットのダウンロードに失敗しました。");
  return response.blob();
}

export async function importFaqs(file: File): Promise<FaqImportResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${apiBase}/api/v1/faqs/import`, { method: "POST", body: formData });
  if (!response.ok) return parseError(response, "FAQの一括登録／更新に失敗しました。");
  return response.json();
}
