export type PostAgentHubUpdateParams = {
  channel: string;
  url: string;
  branch: string;
  authorization: string;
};

export type PostAgentQueryParams = {
  page_index?: number;
  page_size?: number;
  name?: string;
  description?: string;
  author?: string;
  email?: string;
  type?: string;
  version?: string;
  storage_channel?: string;
  storage_url?: string;
};

export type PostDbgptMyQueryParams = {
  type: string | undefined;
  name: string | undefined;
  page_index: number;
  page_size: number;
};

export type IAgentPlugin = {
  name: string;
  description: string;
  email: string;
  version: string;
  storage_url: string;
  download_param: string;
  installed: number;
  id: number;
  author: string;
  type: string;
  storage_channel: string;
  gmt_created: string;
};

export type PostAgentPluginResponse = {
  page_index: number;
  page_size: number;
  total_page: number;
  total_row_count: number;
  datas: IAgentPlugin[];
  items: IAgentPlugin[];
};

export type IMyPlugin = {
  user_name: null | string;
  id: number;
  file_name: string;
  version: string;
  succ_count: number;
  name: string;
  tenant: null | string;
  user_code: string;
  type: string;
  use_count: number;
  created_at: string;
  description: string;
  data?: any; 
};

export type PostAgentMyPluginResponse = {
  items: IMyPlugin[];
}

export type GetDBGPTsListResponse = {
  app_code: string;
  app_describe: string;
  app_name: string;

  language: string;
  sys_code: string;
  updated_at: string;
  team_mode: string;
  id: number;
  user_code: string;
  created_at: string;
}[];
