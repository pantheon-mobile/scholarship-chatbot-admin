import { FileUploadApiError, FileUploadForm, FileUploadResponse } from "@/types/dataSourceFileUpload";
import { authenticatedFetch } from "@/lib/authenticatedFetch";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";

export async function createFileDataSources(values: FileUploadForm): Promise<FileUploadResponse> {
  const form = new FormData();
  values.files.forEach((file) => form.append("files", file));
  if (values.title.trim()) form.append("title", values.title.trim());
  if (values.category_id) form.append("category_id", values.category_id);
  for (const key of ["type_1_value_id", "type_2_value_id", "type_3_value_id"] as const) {
    if (values[key]) form.append(key, values[key]);
  }
  form.append("priority", values.priority);
  form.append("answer_source_enabled", String(values.answer_source_enabled));
  form.append("reference_link_visible", String(values.reference_link_visible));

  const response = await authenticatedFetch(`${apiBase}/api/v1/data-sources/files`, { method: "POST", body: form });
  if (!response.ok) {
    let message = "ファイルの追加に失敗しました。";
    let code: string | undefined;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (body.detail) {
        message = body.detail.message ?? message;
        code = body.detail.code;
      }
    } catch {}
    throw new FileUploadApiError(message, response.status, code);
  }
  return response.json();
}
