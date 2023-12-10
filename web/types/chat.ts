type ChartValue = {
  name: string;
  type: string;
  value: number;
};

/**
 * dashboard chart type
 */
export type ChartData = {
  chart_desc: string;
  chart_name: string;
  chart_sql: string;
  chart_type: string;
  chart_uid: string;
  column_name: Array<string>;
  values: Array<ChartValue>;
};

export type SceneResponse = {
  chat_scene: string;
  param_title: string;
  scene_describe: string;
  scene_name: string;
  show_disable: boolean;
};

export type NewDialogueParam = {
  chat_mode: string;
  model?: string;
};

export type ChatHistoryResponse = IChatDialogueMessageSchema[];

export type IChatDialogueSchema = {
  conv_uid: string;
  user_input: string;
  user_name: string;
  chat_mode: 'chat_with_db_execute' | 'chat_excel' | 'chat_with_db_qa' | 'chat_knowledge' | 'chat_dashboard' | 'chat_execution' | 'chat_agent';
  select_param: string;
};

export type DialogueListResponse = IChatDialogueSchema[];

export type IChatDialogueMessageSchema = {
  role: 'human' | 'view' | 'system' | 'ai';
  context: string;
  order: number;
  time_stamp: number | string | null;
  model_name: string;
  retry?: boolean;
};

export type ModelType =
  | 'proxyllm'
  | 'flan-t5-base'
  | 'vicuna-13b'
  | 'vicuna-7b'
  | 'vicuna-13b-v1.5'
  | 'vicuna-7b-v1.5'
  | 'codegen2-1b'
  | 'codet5p-2b'
  | 'chatglm-6b-int4'
  | 'chatglm-6b'
  | 'chatglm2-6b'
  | 'chatglm2-6b-int4'
  | 'guanaco-33b-merged'
  | 'falcon-40b'
  | 'gorilla-7b'
  | 'gptj-6b'
  | 'proxyllm'
  | 'chatgpt_proxyllm'
  | 'bard_proxyllm'
  | 'claude_proxyllm'
  | 'wenxin_proxyllm'
  | 'tongyi_proxyllm'
  | 'zhipu_proxyllm'
  | 'llama-2-7b'
  | 'llama-2-13b'
  | 'llama-2-70b'
  | 'baichuan-7b'
  | 'baichuan-13b'
  | 'baichuan2-7b'
  | 'baichuan2-13b'
  | 'wizardlm-13b'
  | 'llama-cpp'
  | (string & {});

export type LLMOption = { label: string; icon: string };

export type FeedBack = {
  information?: string;
  just_fun?: string;
  others?: string;
  work_study?: string;
};

export type Reference = {
  name: string;
  chunks: Array<number>;
};

export type IDB = {
  param: string;
  type: string;
};
