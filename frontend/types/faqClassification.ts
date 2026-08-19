export type FaqClassificationValue = {
  id: number;
  value_name: string;
  display_order: number;
  version: number;
};

export type FaqClassificationType = {
  id: number;
  type_code: string;
  fixed_name: string;
  display_label: string;
  display_order: number;
  version: number;
  values: FaqClassificationValue[];
};

export class FaqClassificationApiError extends Error {
  constructor(message: string, public status: number, public code?: string) {
    super(message);
  }
}
