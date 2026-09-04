import { ChatAnswer, ChatHistoryDetail, ChatHistorySummary, ChatUiConfig } from "@/types/chat";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";

async function detail(response: Response) {
  try { const body = await response.json(); return typeof body.detail === "string" ? body.detail : "回答を取得できませんでした。"; }
  catch { return "回答を取得できませんでした。"; }
}

export async function sendChatMessage(question: string, bedrockSessionId?: string): Promise<ChatAnswer> {
  const response = await fetch(`${apiBase}/api/v1/chat/messages`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, bedrock_session_id: bedrockSessionId || null }) });
  if (!response.ok) throw new Error(await detail(response));
  return response.json();
}

async function analytics(path: string, method: string, body: unknown) {
  const response = await fetch(`${apiBase}/api/v1/analytics/${path}`, { method, credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!response.ok) throw new Error("利用状況を記録できませんでした。");
}

export const recordChatAccess = (id: string, identifier: string, at: string) => analytics("accesses", "POST", { id, identity: { identity_kind: "AUTHENTICATED", identifier }, accessed_at: at });
export const startTrackedChat = (id: string, identifier: string, at: string) => analytics("chat-sessions", "POST", { id, identity: { identity_kind: "AUTHENTICATED", identifier }, started_at: at });
export const startTrackedInteraction = (sessionId: string, id: string, sequence: number, at: string, question: string) => analytics(`chat-sessions/${sessionId}/interactions`, "POST", { id, sequence_number: sequence, question_submitted_at: at, question_text: question });
export const completeTrackedInteraction = (id: string, answerType: string | null, at?: string, answer?: string, citations?: unknown[], faqId?: number | null) => analytics(`interactions/${id}/completion`, "PATCH", answerType ? { processing_status: "COMPLETED", answer_type: answerType, answer_displayed_at: at, answer_text: answer, citations: citations ?? [], faq_id: faqId ?? null } : { processing_status: "FAILED" });
export const submitFeedback = (id: string, rating: "GOOD" | "BAD", comment?: string) => analytics(`interactions/${id}/feedback`, "PUT", { rating, comment: comment || null });

async function chatGet<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBase}/api/v1/chat/${path}`, { credentials: "include" });
  if (!response.ok) throw new Error(await detail(response));
  return response.json();
}

async function chatWrite<T>(path: string, method: string, body?: unknown): Promise<T> {
  const response = await fetch(`${apiBase}/api/v1/chat/${path}`, { method, credentials: "include", headers: body === undefined ? undefined : { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!response.ok) throw new Error(await detail(response));
  return response.status === 204 ? undefined as T : response.json();
}

export const fetchChatConfig = () => chatGet<ChatUiConfig>("config");
export const fetchChatHistory = (search = "") => chatGet<ChatHistorySummary[]>(`sessions${search.trim() ? `?search=${encodeURIComponent(search.trim())}` : ""}`);
export const fetchChatHistoryDetail = (id: string) => chatGet<ChatHistoryDetail>(`sessions/${id}`);
export const updateChatHistoryTitle = (id: string, title: string) => chatWrite<ChatHistorySummary>(`sessions/${id}`, "PATCH", { title });
export const deleteChatHistory = (id: string) => chatWrite<void>(`sessions/${id}`, "DELETE");
