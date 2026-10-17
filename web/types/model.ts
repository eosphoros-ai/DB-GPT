import { ConfigurableParams } from '@/types/common';

export type IModelData = {
  chat_scene: string;
  model_name: string;
  worker_type: string;
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
  delete_after: boolean | null;
  params: any;
};

export type ModelParams = {
  [key: string]: string | number | boolean;
};

export type StartModelParams = {
  host: string;
  port: number;
  model: string;
  worker_type: string;
  params: ModelParams;
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
  params: ConfigurableParams;
  provider: string;
  description: string;
};

export type ProviderModel = {
  model: string;
  label: string;
  context_length: number | null;
  max_output_length: number | null;
  function_calling: boolean | null;
  link: string | null;
  description: string | null;
  enabled: boolean;
};

export type ModelProvider = {
  provider: string;
  name: string;
  worker_type: string;
  proxy: boolean;
  params: ConfigurableParams[];
  models: ProviderModel[];
};

export type ProviderConfig = {
  provider: string;
  connected: boolean;
  api_base: string | null;
  enabled_models: string[];
};

export interface ModelIconInfo {
  label: string;
  icon: string;
  patterns?: string[]; // The patterns that the model name may contain
}
