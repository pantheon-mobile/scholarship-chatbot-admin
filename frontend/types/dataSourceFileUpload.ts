import { DataSource } from "./dataSource";

export type FileUploadForm = {
  files: File[];
  title: string;
  type_1_value_id: string;
  type_2_value_id: string;
  type_3_value_id: string;
  priority: "HIGH" | "MEDIUM" | "LOW";
  answer_source_enabled: boolean;
  reference_link_visible: boolean;
};

export type FileUploadResponse = {
  items: DataSource[];
  created_count: number;
};

export class FileUploadApiError extends Error {
  constructor(message: string, public status: number, public code?: string) {
    super(message);
  }
}
