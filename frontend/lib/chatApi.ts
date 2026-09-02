import { ChatAnswer } from "@/types/chat";

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
export const startTrackedInteraction = (sessionId: string, id: string, sequence: number, at: string) => analytics(`chat-sessions/${sessionId}/interactions`, "POST", { id, sequence_number: sequence, question_submitted_at: at });
export const completeTrackedInteraction = (id: string, answerType: string | null, at?: string) => analytics(`interactions/${id}/completion`, "PATCH", answerType ? { processing_status: "COMPLETED", answer_type: answerType, answer_displayed_at: at } : { processing_status: "FAILED" });
export const submitFeedback = (id: string, rating: "GOOD" | "BAD") => analytics(`interactions/${id}/feedback`, "PUT", { rating, comment: null });
