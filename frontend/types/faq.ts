export type FaqSortColumn = "id" | "updated_at";
export type SortOrder = "asc" | "desc";

export type FaqClassification = {
  type_code: string;
  classification_type_id: number;
  classification_value_id: number;
  display_label: string;
  value_name: string;
};

export type Faq = {
  id: number;
  question: string;
  answer: string;
  chat_enabled: boolean;
  updated_at: string;
  version: number;
  classifications: FaqClassification[];
};

export type FaqSimilarQuestion = { id: number; question: string; display_order: number };
export type FaqDetail = Faq & { created_at: string; similar_questions: FaqSimilarQuestion[] };

export type FaqCreate = {
  question: string;
  answer: string;
  similar_questions: string[];
  classification_1_value_id: number | null;
  classification_2_value_id: number | null;
  classification_3_value_id: number | null;
  classification_4_value_id: number | null;
  chat_enabled: boolean;
};

export type FaqFilters = {
  keyword: string;
  classification_1_value_id: string;
  classification_2_value_id: string;
  classification_3_value_id: string;
  classification_4_value_id: string;
  chat_enabled: string;
  sort: FaqSortColumn;
  order: SortOrder;
  page: number;
  page_size: number;
};

export type FaqListResponse = {
  items: Faq[];
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
  sort: FaqSortColumn;
  order: SortOrder;
};

export class FaqApiError extends Error {
  constructor(message: string, public status: number, public code?: string) {
    super(message);
  }
}
