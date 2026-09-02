/** 管理API呼び出し時に、CPF認証後のセッションCookieを必ず送信する。 */
export function authenticatedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  return fetch(input, { ...init, credentials: "include" });
}
