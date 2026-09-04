export type ChatCitation = { title: string; uri?: string | null; excerpt?: string | null };
export type ChatAnswer = { answer: string; answer_type: "FAQ" | "GENERATED_AI" | "NO_ANSWER"; faq_id?: number | null; bedrock_session_id?: string | null; citations: ChatCitation[] };
export type ChatMessage = { id: string; role: "user" | "assistant"; content: string; sentAt: string; citations?: ChatCitation[]; interactionId?: string; rating?: "GOOD" | "BAD"; answerType?: "FAQ" | "GENERATED_AI" | "NO_ANSWER" };
export type ChatUiConfig = {
  title: string; initial_message: string; input_placeholder: string; question_max_length: number;
  frame_color: string; bot_icon_url?: string | null; history_enabled: boolean;
  maintenance_enabled: boolean; maintenance_message: string;
  good_message: string; bad_message: string; good_options: string[]; bad_options: string[];
};
export type ChatHistorySummary = { id: string; title: string; started_at: string; updated_at: string };
export type ChatHistoryDetail = { id: string; title: string; messages: Array<{
  id: string; role: "user" | "assistant"; content: string; sent_at: string; citations: ChatCitation[];
  interaction_id?: string | null; rating?: "GOOD" | "BAD" | null; answer_type?: "FAQ" | "GENERATED_AI" | "NO_ANSWER" | null;
}> };
