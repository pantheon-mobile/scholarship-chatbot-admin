export type ChatHistoryItem = {
  session_id: string;
  user_label: string;
  user_id: string | null;
  user_name: string | null;
  user_role: string | null;
  user_site: string | null;
  started_at: string;
  ended_at: string | null;
  response_count: number;
  completed_count: number;
  failed_count: number;
  faq_count: number;
  generated_ai_count: number;
  no_answer_count: number;
  good_count: number;
  bad_count: number;
};

export type ChatHistoryResponse = {
  from_date: string;
  to_date: string;
  page: number;
  page_size: number;
  total_count: number;
  items: ChatHistoryItem[];
};
