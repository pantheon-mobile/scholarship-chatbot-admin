import { Category, CategoryApiError, CategoryDeleteTarget, CategoryListResponse } from "@/types/category";

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
  throw new CategoryApiError(message, response.status, code);
}

export async function fetchCategories(): Promise<CategoryListResponse> {
  const response = await fetch(`${apiBase}/api/v1/categories`, { cache: "no-store" });
  if (!response.ok) return parseError(response, "カテゴリ一覧の取得に失敗しました。");
  return response.json();
}

export async function deleteCategory(id: number, version: number): Promise<void> {
  const response = await fetch(`${apiBase}/api/v1/categories/${id}?version=${version}`, { method: "DELETE" });
  if (!response.ok) return parseError(response, "カテゴリの削除に失敗しました。");
}

export async function bulkDeleteCategories(items: CategoryDeleteTarget[]): Promise<number> {
  const response = await fetch(`${apiBase}/api/v1/categories/bulk-delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items }),
  });
  if (!response.ok) return parseError(response, "選択したカテゴリの削除に失敗しました。");
  return (await response.json()).deleted_count;
}

export async function reorderCategories(parentId: number | null, items: CategoryDeleteTarget[]): Promise<Category[]> {
  const response = await fetch(`${apiBase}/api/v1/categories/order`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ parent_id: parentId, items }),
  });
  if (!response.ok) return parseError(response, "カテゴリの並び替えに失敗しました。");
  return response.json();
}

export async function exportCategories(): Promise<{ blob: Blob; fileName: string }> {
  const response = await fetch(`${apiBase}/api/v1/categories/export`);
  if (!response.ok) return parseError(response, "カテゴリ一覧のダウンロードに失敗しました。");
  const disposition = response.headers.get("content-disposition") ?? "";
  const fileName = disposition.match(/filename="?([^";]+)"?/i)?.[1] ?? "category.xlsx";
  return { blob: await response.blob(), fileName };
}
