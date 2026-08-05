export interface ClassificationValue {
  id: number;
  value_name: string;
  display_order: number;
  version: number;
}

export interface ClassificationType {
  id: number;
  type_code: string;
  fixed_name: string;
  display_label: string;
  display_order: number;
  version: number;
  values: ClassificationValue[];
}
