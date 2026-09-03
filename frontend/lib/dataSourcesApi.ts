import { DataSource, DataSourceFilters, DataSourceListResponse, DataSourcesApiError, FileDataSourceUpdate, WebsiteDataSourceCreate, WebsiteDataSourceUpdate } from "@/types/dataSource";
import { authenticatedFetch } from "@/lib/authenticatedFetch";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";

function queryString(filters: DataSourceFilters, includePage = true) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (!includePage && (key === "page" || key === "page_size")) continue;
    if (value !== "" && value !== null && value !== undefined) params.set(key, String(value));
  }
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
  throw new DataSourcesApiError(message, response.status, code);
}

export async function fetchDataSources(filters: DataSourceFilters): Promise<DataSourceListResponse> {
  const response = await authenticatedFetch(`${apiBase}/api/v1/data-sources?${queryString(filters)}`, { cache: "no-store" });
  if (!response.ok) return parseError(response, "データソース一覧の取得に失敗しました。");
  return response.json();
}

export async function runIngestionNow(): Promise<{ message: string }> {
  const response = await authenticatedFetch(`${apiBase}/api/v1/data-sources/ingestion/run-now`, {
    method: "POST",
  });
  if (!response.ok) return parseError(response, "取り込み処理を開始できませんでした。");
  return response.json();
}

export async function fetchDataSource(id: number): Promise<DataSource> {
  const response = await authenticatedFetch(`${apiBase}/api/v1/data-sources/${id}`, { cache: "no-store" });
  if (!response.ok) return parseError(response, "データソース情報の取得に失敗しました。");
  return response.json();
}

export async function updateFileDataSource(id: number, values: FileDataSourceUpdate): Promise<DataSource> {
  const response = await authenticatedFetch(`${apiBase}/api/v1/data-sources/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  });
  if (!response.ok) return parseError(response, "データソースの更新に失敗しました。");
  return response.json();
}

export async function createWebsiteDataSource(values: WebsiteDataSourceCreate): Promise<DataSource> {
  const response = await authenticatedFetch(`${apiBase}/api/v1/data-sources/websites`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  });
  if (!response.ok) return parseError(response, "Webサイトの追加に失敗しました。");
  return response.json();
}

export async function updateWebsiteDataSource(id: number, values: WebsiteDataSourceUpdate): Promise<DataSource> {
  const response = await authenticatedFetch(`${apiBase}/api/v1/data-sources/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  });
  if (!response.ok) return parseError(response, "Webサイトの更新に失敗しました。");
  return response.json();
}

export async function updateAnswerSource(id: number, enabled: boolean, version: number): Promise<DataSource> {
  const response = await authenticatedFetch(`${apiBase}/api/v1/data-sources/${id}/answer-source`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled, version }),
  });
  if (!response.ok) return parseError(response, "回答ソースの更新に失敗しました。");
  return response.json();
}

export async function updateReferenceLink(id: number, visible: boolean, version: number): Promise<DataSource> {
  const response = await authenticatedFetch(`${apiBase}/api/v1/data-sources/${id}/reference-link`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ visible, version }),
  });
  if (!response.ok) return parseError(response, "参照リンクの更新に失敗しました。");
  return response.json();
}

export async function deleteDataSource(id: number, version: number): Promise<void> {
  const response = await authenticatedFetch(`${apiBase}/api/v1/data-sources/${id}?version=${version}`, { method: "DELETE" });
  if (!response.ok) return parseError(response, "データソースの削除に失敗しました。");
}

export async function bulkDeleteDataSources(items: Array<{ id: number; version: number }>): Promise<number> {
  const response = await authenticatedFetch(`${apiBase}/api/v1/data-sources/bulk-delete`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items }),
  });
  if (!response.ok) return parseError(response, "選択したデータソースの削除に失敗しました。");
  return (await response.json()).deleted_count;
}

export async function exportDataSources(filters: DataSourceFilters): Promise<Blob> {
  const response = await authenticatedFetch(`${apiBase}/api/v1/data-sources/export?${queryString(filters, false)}`);
  if (!response.ok) return parseError(response, "一覧のダウンロードに失敗しました。");
  return response.blob();
}
