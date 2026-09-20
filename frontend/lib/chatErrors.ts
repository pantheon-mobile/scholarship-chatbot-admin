export const CONNECTION_ERROR_MESSAGE = "接続エラーにより、回答を取得できませんでした。インターネット接続を確認し、時間をおいてもう一度質問を送信してください。解消しない場合は、システム管理者にお問い合わせください。";

export function questionErrorMessage(reason: unknown): string {
  // Fetch failures differ across Chrome, Firefox and Safari. Preserve API errors.
  if (reason instanceof TypeError && /^(Failed to fetch|Load failed|NetworkError when attempting to fetch resource\.?|Network request failed)$/i.test(reason.message)) {
    return CONNECTION_ERROR_MESSAGE;
  }
  return reason instanceof Error ? reason.message : "回答を取得できませんでした。";
}
