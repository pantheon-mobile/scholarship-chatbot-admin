import { AuthenticatedUser, DevelopmentCpfLogin } from "@/types/auth";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";

async function parseError(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    return typeof payload.detail === "string" ? payload.detail : "認証に失敗しました。";
  } catch {
    return "認証に失敗しました。";
  }
}

export async function exchangeCpfToken(token: string): Promise<AuthenticatedUser> {
  const response = await fetch(`${apiBase}/api/v1/auth/cpf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ token }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function loginWithDevelopmentCpf(payload: DevelopmentCpfLogin): Promise<AuthenticatedUser> {
  const tokenResponse = await fetch(`${apiBase}/api/v1/auth/development/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!tokenResponse.ok) throw new Error(await parseError(tokenResponse));
  const { token } = await tokenResponse.json() as { token: string };
  const sessionResponse = await fetch(`${apiBase}/api/v1/auth/development/cpf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ token }),
  });
  if (!sessionResponse.ok) throw new Error(await parseError(sessionResponse));
  return sessionResponse.json();
}

export async function fetchAuthenticatedUser(): Promise<AuthenticatedUser> {
  const response = await fetch(`${apiBase}/api/v1/auth/session`, {
    cache: "no-store",
    credentials: "include",
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function logout(): Promise<void> {
  await fetch(`${apiBase}/api/v1/auth/session`, {
    method: "DELETE",
    credentials: "include",
  });
}
