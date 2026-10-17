interface ExtMetadata {
  tags: string;
  order: number;
  [key: string]: string | number | boolean;
}

type NestedField = {
  [key: string]: ConfigurableParams;
};

export type ConfigurableParams = {
  param_class: string;
  param_name: string;
  param_type: string;
  default_value: string | boolean | number;
  description: string;
  required: boolean;
  valid_values: null | string[];
  ext_metadata: ExtMetadata;
  is_array: boolean;
  label: string;
  nested_fields: NestedField | null;
};
