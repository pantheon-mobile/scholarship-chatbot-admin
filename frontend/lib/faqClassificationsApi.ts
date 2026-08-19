import { FaqClassificationApiError, FaqClassificationType } from "@/types/faqClassification";

const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  throw new FaqClassificationApiError(message, response.status, code);
}

export async function fetchFaqClassifications(): Promise<FaqClassificationType[]> {
  const response = await fetch(`${apiBase}/api/v1/faq-classifications`, { cache: "no-store" });
  if (!response.ok) return parseError(response, "区分一覧の取得に失敗しました。");
  return (await response.json()).items;
}

export async function updateFaqClassificationLabel(typeId: number, displayLabel: string, version: number): Promise<FaqClassificationType> {
  const response = await fetch(`${apiBase}/api/v1/faq-classifications/${typeId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ display_label: displayLabel, version }),
  });
  if (!response.ok) return parseError(response, "区分ラベルの更新に失敗しました。");
  return response.json();
}

export async function addFaqClassificationValue(typeId: number, valueName: string): Promise<FaqClassificationType> {
  const response = await fetch(`${apiBase}/api/v1/faq-classifications/${typeId}/values`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value_name: valueName }),
  });
  if (!response.ok) return parseError(response, "区分値の追加に失敗しました。");
  return response.json();
}

export async function updateFaqClassificationValue(typeId: number, valueId: number, valueName: string, version: number): Promise<FaqClassificationType> {
  const response = await fetch(`${apiBase}/api/v1/faq-classifications/${typeId}/values/${valueId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value_name: valueName, version }),
  });
  if (!response.ok) return parseError(response, "区分値の更新に失敗しました。");
  return response.json();
}

export async function deleteFaqClassificationValue(typeId: number, valueId: number, version: number): Promise<void> {
  const response = await fetch(`${apiBase}/api/v1/faq-classifications/${typeId}/values/${valueId}?version=${version}`, { method: "DELETE" });
  if (!response.ok) return parseError(response, "区分値の削除に失敗しました。");
}

export async function reorderFaqClassificationValues(typeId: number, items: Array<{ id: number; version: number }>): Promise<FaqClassificationType> {
  const response = await fetch(`${apiBase}/api/v1/faq-classifications/${typeId}/values/order`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items }),
  });
  if (!response.ok) return parseError(response, "並び替えの保存に失敗しました。");
  return response.json();
}

export async function exportFaqClassifications(): Promise<Blob> {
  const response = await fetch(`${apiBase}/api/v1/faq-classifications/export`);
  if (!response.ok) return parseError(response, "区分一覧のダウンロードに失敗しました。");
  return response.blob();
}
