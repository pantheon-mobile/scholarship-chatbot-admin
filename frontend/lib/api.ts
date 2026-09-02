import { ClassificationType } from "@/types/dataSourceTypes";
import { authenticatedFetch } from "@/lib/authenticatedFetch";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";

export async function fetchDataSourceTypes(): Promise<ClassificationType[]> {
  const res = await authenticatedFetch(`${apiBase}/api/v1/data-source-types`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error("一覧の取得に失敗しました。");
  }
  return res.json();
}

export async function updateTypeLabel(typeId: number, display_label: string, version: number): Promise<ClassificationType> {
  const res = await authenticatedFetch(`${apiBase}/api/v1/data-source-types/${typeId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ display_label, version }),
  });
  if (!res.ok) {
    throw new Error("種別ラベルの更新に失敗しました。");
  }
  return res.json();
}

export async function addClassificationValue(typeId: number, value_name: string): Promise<ClassificationType> {
  const res = await authenticatedFetch(`${apiBase}/api/v1/data-source-types/${typeId}/values`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value_name }),
  });
  if (!res.ok) {
    throw new Error("種別値の追加に失敗しました。");
  }
  return res.json();
}

export async function updateClassificationValue(typeId: number, valueId: number, value_name: string, version: number): Promise<ClassificationType> {
  const res = await authenticatedFetch(`${apiBase}/api/v1/data-source-types/${typeId}/values/${valueId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value_name, version }),
  });
  if (!res.ok) {
    throw new Error("種別値の更新に失敗しました。");
  }
  return res.json();
}

export async function deleteClassificationValue(typeId: number, valueId: number, version: number): Promise<void> {
  const res = await authenticatedFetch(`${apiBase}/api/v1/data-source-types/${typeId}/values/${valueId}?version=${version}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error("種別値の削除に失敗しました。");
  }
}

export async function reorderClassificationValues(typeId: number, orderedIds: number[]): Promise<void> {
  const res = await authenticatedFetch(`${apiBase}/api/v1/data-source-types/${typeId}/values/order`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(orderedIds),
  });
  if (!res.ok) {
    throw new Error("並び替えの保存に失敗しました。");
  }
}

export async function exportClassificationTypes(): Promise<Blob> {
  const res = await authenticatedFetch(`${apiBase}/api/v1/data-source-types/export`);
  if (!res.ok) {
    throw new Error("Excelのダウンロードに失敗しました。");
  }
  return res.blob();
}
