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
  team_context: string;
  /**
   * 应用节点信息
   */
  details?: IDetail[];
  /**
   * 是否已收藏
   */
  is_collected: string;
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
};

export type ITeamModal = {
  auto_plan: string;
  awel_layout: string;
  singe_agent: string;
};

export type IResource = {
  is_dynamic: boolean;
  name: string;
  type: string;
  value: string;
};

export type IDetail = {
  agent_name?: string;
  app_code?: string;
  llm_strategy?: string;
  llm_strategy_value?: string;
  resources?: IResource[];
  key?: string;
};
