export const CONNECTION_ERROR_MESSAGE = "接続エラーにより、回答を取得できませんでした。インターネット接続を確認し、時間をおいてもう一度質問を送信してください。解消しない場合は、システム管理者にお問い合わせください。";

export function questionErrorMessage(reason: unknown): string {
  // Fetch failures differ across Chrome, Firefox and Safari. Preserve API errors.
  if (reason instanceof TypeError && /^(Failed to fetch|Load failed|NetworkError when attempting to fetch resource\.?|Network request failed)$/i.test(reason.message)) {
    return CONNECTION_ERROR_MESSAGE;
  }
  return reason instanceof Error ? reason.message : "回答を取得できませんでした。";
}


export const QUESTION_REJECTED_MESSAGE = "質問を送信できませんでした。解消しない場合は、システム管理者にお問い合わせください。";

export async function questionResponseError(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
  } catch { /* Do not expose a proxy's HTML error page. */ }
  if (response.status === 401) return "認証が必要です。CPFのメニューからログインし直してください。";
  if (response.status === 403) return QUESTION_REJECTED_MESSAGE;
  return fallback;
}
