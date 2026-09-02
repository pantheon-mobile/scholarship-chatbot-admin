export type ChatCitation = { title: string; uri?: string | null; excerpt?: string | null };
export type ChatAnswer = { answer: string; answer_type: "FAQ" | "GENERATED_AI" | "NO_ANSWER"; bedrock_session_id?: string | null; citations: ChatCitation[] };
export type ChatMessage = { id: string; role: "user" | "assistant"; content: string; citations?: ChatCitation[]; interactionId?: string; rating?: "GOOD" | "BAD" };
