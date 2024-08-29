// app
export type IApp = {
  app_code: string;
  /**
   * 应用名
   */
  app_name: string;
  /**
   * 应用描述信息/简介
   */
  app_describe: string;
  /**
   * 语言/prompt关联
   */
  language: 'en' | 'zh';
  /**
   * 组织模式（AutoPlan/LayOut）
   */
  team_mode: string;
  /**
   * 组织上下文/ None
   */
  team_context: Record<string, any>;
  /**
   * 应用节点信息
   */
  details?: IDetail[];
  /**
   * 是否已收藏
   */
  is_collected: string;
  /**
   * 是否已发布
   */
  updated_at: string;
  hot_value: number;
  owner_name?: string;
  owner_avatar_url?: string;
  published?: string;
  param_need: ParamNeed[];
  recommend_questions?: Record<string, any>[];
  conv_uid?: string;
};

export type IAppData = {
  app_list: IApp[];
  current_page: number;
  total_count: number;
  total_page: number;
};

// agent
export type AgentParams = {
  agent_name: string;
  node_id: string;
  /**
   * Agent绑定的资源
   */
  resources: string;
  /**
   * Agent的绑定模板
   */
  prompt_template: string;
  /**
   * llm的使用策略，默认是priority
   */
  llm_strategy: string;
  /**
   * 策略包含的参数
   */
  llm_strategy_value: string;
};

export type IAgent = {
  describe?: string;
  name: string;
  system_message?: string;
  label?: string;
  desc?: string;
};

export type ITeamModal = {
  auto_plan: string;
  awel_layout: string;
  singe_agent: string;
};

export type IResource = {
  is_dynamic?: boolean;
  name?: string;
  type?: string;
  value?: string;
};

export type IDetail = {
  agent_name?: string;
  app_code?: string;
  llm_strategy?: string;
  llm_strategy_value?: string;
  resources?: IResource[];
  key?: string;
  prompt_template?: string;
  recommend_questions?: string[];
};

export interface GetAppInfoParams {
  chat_scene: string;
  app_code: string;
}

export interface TeamMode {
  name: string;
  value: string;
  name_cn: string;
  name_en: string;
  description: string;
  description_en: string;
  remark: string;
}

export interface CreateAppParams {
  app_describe?: string;
  app_name?: string;
  team_mode?: string;
  app_code?: string;
  details?: IDetail[];
  language?: 'zh' | 'en';
  recommend_questions?: [];
  team_context?: Record<string, any>;
  param_need?: ParamNeed[];
}

export interface AppListResponse {
  app_list: IApp[];
  current_page: number;
  total_page: number;
  total_count: number;
}

export interface StrategyResponse extends Omit<TeamMode, 'remark'> {}

export interface ParamNeed {
  type: string;
  value: any;
  bind_value?: string;
}

export interface NativeAppScenesResponse {
  chat_scene: string;
  scene_name: string;
  param_need: ParamNeed[];
}
