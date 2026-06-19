// app
export type IApp = {
  app_code: string;
  /**
   * App name
   */
  app_name: string;
  /**
   * App description / summary
   */
  app_describe: string;
  /**
   * Language / prompt association
   */
  language: 'en' | 'zh';
  /**
   * Organization mode (AutoPlan/LayOut)
   */
  team_mode: string;
  /**
   * Organization context / None
   */
  team_context: Record<string, any>;
  /**
   * App node information
   */
  details?: IDetail[];
  /**
   * Whether favorited
   */
  is_collected: string;
  /**
   * Whether published
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
   * Resources bound to the agent
   */
  resources: string;
  /**
   * Prompt template bound to the agent
   */
  prompt_template: string;
  /**
   * LLM usage strategy, defaults to priority
   */
  llm_strategy: string;
  /**
   * Parameters included in the strategy
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
  total_count: number;
  app_list: IApp[];
  current_page: number;
  total_page: number;
}

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
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
