export type TabKey = 'all';

// 评估列表项接口
export interface BenchmarkConfig {
  file_parse_type: string;
  format_type: string;
  content_type: string;
  benchmark_mode_type: string;
  output_file_path: string;
  standard_file_path: string;
  round_time: number;
  generate_ratio: number;
  execute_llm_result: boolean;
  invoke_llm: boolean;
  llm_thread_map: Record<string, number>;
  compare_result_enable: boolean;
  compare_config: null;
  thread_num: number;
  user_id: null;
  evaluate_code: string;
  scene_key: string;
}

export interface EvaluationItem {
  evaluate_code: string;
  scene_key: string;
  scene_value: string;
  datasets_name: string;
  datasets: null;
  evaluate_metrics: null;
  context: {
    benchmark_config: string; // JSON字符串
  };
  user_name: null;
  user_id: null;
  sys_code: string;
  parallel_num: null;
  state: string;
  result: string;
  storage_type: string;
  average_score: null;
  log_info: null;
  gmt_create: string;
  gmt_modified: string;
  round_time: number;
}

export interface EvaluationData {
  items: EvaluationItem[];
  total_count: number;
  total_pages: number;
  page: number;
  page_size: number;
}

export interface ModelsEvaluationResponse {
  success: boolean;
  err_code: null;
  err_msg: null;
  data: EvaluationData;
}

export interface getBenchmarkTaskListRequest {
  page: number;
  page_size: number;
  filter_param?: string;
  sys_code?: string;
}

// 新的创建评测任务请求类型
export type createBenchmarkTaskRequest = {
  scene_value: string;
  benchmark_type: string;
  // LLM 评测相关字段 (可选)
  model_list?: string[];
  temperature?: number;
  max_tokens?: number;
  // Agent 评测相关字段 (可选)
  api_url?: string;
  headers?: Record<string, any>;
  parse_strategy?: string;
  response_mapping?: Record<string, any>;
  http_method?: string;
  timeout?: number;
  max_retries?: number;
};
