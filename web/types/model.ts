export type IModelData = {
  chat_scene: string;
  model_name: string;
  model_type: string;
  host: string;
  port: number;
  manager_host: string;
  manager_port: number;
  healthy: boolean;
  check_healthy: boolean;
  prompt_template: string;
  last_heartbeat: string;
  stream_api: string;
  nostream_api: string;
};

export type BaseModelParams = {
  host: string;
  port: number;
  model: string;
  worker_type: string;
  params: any;
};

export type ModelParams = {
  model_name: string;
  model_path: string;
  proxy_api_key: string;
  proxy_server_url: string;
  model_type: string;
  max_context_size: number;
};

export type StartModelParams = {
  host: string;
  port: number;
  model: string;
  worker_type: string;
  params: ModelParams;
};

interface ExtMetadata {
  tags: string;
}

export type SupportModelParams = {
  param_class: string;
  param_name: string;
  param_type: string;
  default_value: string | boolean | number;
  description: string;
  required: boolean;
  valid_values: null;
  ext_metadata: ExtMetadata;
};

export type SupportModel = {
  model: string;
  path: string;
  worker_type: string;
  path_exist: boolean;
  proxy: boolean;
  enabled: boolean;
  host: string;
  port: number;
  params: SupportModelParams;
};
