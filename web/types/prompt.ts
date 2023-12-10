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
}
