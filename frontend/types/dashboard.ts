export type ResponseTimeMetrics = {
  average_seconds: number | null;
  minimum_seconds: number | null;
  maximum_seconds: number | null;
};

export type BasicMetrics = {
  access_count: number;
  access_user_count: number;
  chat_count: number;
  chat_user_count: number;
  average_chats_per_day: number | null;
  average_chats_per_user: number | null;
  response_count: number;
  average_responses_per_chat: number | null;
  average_responses_per_user: number | null;
  response_time: ResponseTimeMetrics;
  valid_answer_count: number;
  no_answer_count: number;
  answer_rate: number | null;
  good_count: number;
  bad_count: number;
  unrated_count: number;
  satisfaction_rate: number | null;
  comment_count: number;
  good_comment_count: number;
  bad_comment_count: number;
};

export type AnswerTypeMetrics = {
  total_count: number;
  faq_count: number;
  faq_rate: number | null;
  generated_ai_count: number;
  generated_ai_rate: number | null;
  no_answer_count: number;
};

export type DashboardBucket = {
  key: string;
  label: string;
  chat_count: number;
  response_count: number;
};

export type DashboardResponse = {
  period: { from_date: string; to_date: string; timezone: string };
  basic_metrics: BasicMetrics;
  answer_types: AnswerTypeMetrics;
  time_buckets: DashboardBucket[];
  weekday_buckets: DashboardBucket[];
};

export class DashboardApiError extends Error {
  constructor(message: string, public status: number, public code?: string) {
    super(message);
  }
}
