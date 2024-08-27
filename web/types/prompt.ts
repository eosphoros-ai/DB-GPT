export type PromptParams = {
  prompt_type: string;
  current: number;
  pageSize: number;
  hideOnSinglePage: boolean;
  showQuickJumper: boolean;
};

export interface UpdatePromptParams extends IPrompt {
  prompt_type: string;
}

export interface IPrompt {
  chat_scene: string;
  content: string;
  gmt_created: string;
  gmt_modified: string;
  id: number;
  prompt_name: string;
  prompt_type: string;
  sub_chat_scene: string;
  user_name?: string;
  user_id?: string;
}

export interface PromptTemplateProps {
  prompt_type: string;
  target: string;
}

export interface PromptTemplateLoadProps extends PromptTemplateProps {}

export interface PromptResponseVerifyProps {}

export interface PromptTemplateLoadResponse {
  input_variables: string[];
  response_format: string;
  template: string;
  [key: string]: any;
}

export interface OperatePromptParams {
  chat_scene: string;
  sub_chat_scene: string;
  prompt_type: string;
  prompt_name: string;
  content: string;
  prompt_desc: string;
  response_schema: string;
  input_variables: string;
  model: string;
  prompt_language: 'en' | 'zh';
  user_name: string;
}

export interface DebugParams {
  chat_scene: string;
  sub_chat_scene: string;
  prompt_code: string;
  prompt_type: string;
  prompt_name: string;
  content: string;
  prompt_desc: string;
  response_schema: string;
  input_variables: string;
  model: string;
  prompt_language: 'en';
  input_values: Record<string, any>;
  temperature: number;
  debug_model: string;
  user_input: string;
}

export interface LlmOutVerifyParams {
  llm_out: string;
  prompt_type: string;
  chat_scene: string;
}

export interface PromptListResponse {
  items: IPrompt[];
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
}
