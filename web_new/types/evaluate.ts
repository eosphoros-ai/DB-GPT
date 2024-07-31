export type getEvaluationsRequest = {
  filter_param?: string;
  sys_code?: string;
  page: number;
  page_size: number;
};
export type getMetricsRequest = {
  scene_key: string;
  scene_value: string;
};
export type createEvaluationsRequest = {
  evaluate_code: string;
  scene_key: string;
  scene_value: string;
  datasets: string;
  evaluate_metrics: string;
  context: string;
  user_name: string;
  user_id: string;
  sys_code: string;
};
export type delDataSetRequest = {
  code: string;
};
export type delEvaluationRequest = {
  evaluation_code: string;
};
export type downloadEvaluationRequest = {
  evaluate_code: string;
};
export type getDataSetsRequest = getEvaluationsRequest;

export type uploadDataSetsRequest = {
  doc_file?: File;
  content?: string;
  dataset_name: string;
  members: string;
};
export type updateDataSetRequest = {
  code: string;
  members: string;
};
