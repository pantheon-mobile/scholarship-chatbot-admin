export type SourceType = "FILE" | "WEB";
export type DataSourceStatus = "PREPARING" | "TRAINING" | "AVAILABLE" | "ERROR";
export type Priority = "HIGH" | "MEDIUM" | "LOW";
export type SortColumn = "id" | "title" | "updated_at";
export type SortOrder = "asc" | "desc";

export type DataSourceClassification = {
  type_code: string;
  classification_type_id: number;
  classification_value_id: number;
  display_label: string;
  value_name: string;
};

export type DataSource = {
  id: number;
  source_type: SourceType;
  title: string;
  format: string;
  status: DataSourceStatus;
  category_name: string | null;
  size_bytes: number | null;
  character_count: number | null;
  answer_source_enabled: boolean;
  priority: Priority;
  reference_link_visible: boolean;
  updated_at: string;
  version: number;
  file: { file_name: string } | null;
  website: { url: string } | null;
  classifications: DataSourceClassification[];
};

export type DataSourceFilters = {
  keyword: string;
  format: string;
  status: string;
  type_1_value_id: string;
  type_2_value_id: string;
  type_3_value_id: string;
  answer_source_enabled: string;
  priority: string;
  reference_link_visible: string;
  sort: SortColumn;
  order: SortOrder;
  page: number;
  page_size: number;
};

export type DataSourceListResponse = {
  items: DataSource[];
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
  total_size_bytes: number;
  sort: SortColumn;
  order: SortOrder;
};

export type FileDataSourceUpdate = {
  title: string;
  type_1_value_id: number | null;
  type_2_value_id: number | null;
  type_3_value_id: number | null;
  priority: Priority;
  answer_source_enabled: boolean;
  reference_link_visible: boolean;
  version: number;
};

export type WebsiteDataSourceCreate = {
  url: string;
  title: string;
  type_1_value_id: number | null;
  type_2_value_id: number | null;
  type_3_value_id: number | null;
  priority: Priority;
  answer_source_enabled: boolean;
  reference_link_visible: boolean;
};

export class DataSourcesApiError extends Error {
  constructor(message: string, public status: number, public code?: string) {
    super(message);
  }
}
