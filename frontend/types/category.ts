export type Category = {
  id: number;
  name: string;
  parent_id: number | null;
  display_order: number;
  version: number;
  has_children: boolean;
  created_at: string;
  updated_at: string;
};

export type CategoryListResponse = { items: Category[] };
export type CategoryDeleteTarget = { id: number; version: number };

export class CategoryApiError extends Error {
  constructor(message: string, public status: number, public code?: string) {
    super(message);
  }
}
